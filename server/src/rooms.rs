//! Who may read and write a conversation, who gets its pushes, and which
//! other homes it is forwarded to.

use mongodb::bson::DateTime;

use crate::protocol::{parse_conversation, ConvRef, LinkKind, LinkState, Member, ServerMsg};
use crate::store::{LinkDoc, Store};

pub struct Room {
    pub id: String,
    /// The two devices of a direct conversation; empty otherwise.
    pub dm_members: Vec<String>,
    /// Devices on this home that get pushes.
    pub local: Vec<String>,
    /// Links whose other home also stores this conversation.
    pub forward: Vec<LinkDoc>,
}

#[derive(Clone, Copy, PartialEq)]
pub enum Access {
    Read,
    Write,
}

fn denied(msg: &str) -> ServerMsg {
    ServerMsg::error("not_found", msg)
}

fn store_err(e: mongodb::error::Error) -> ServerMsg {
    eprintln!("chat: store error: {e}");
    ServerMsg::error("unavailable", "storage error; try again")
}

pub fn is_local(store: &Store, link: &LinkDoc, side: char) -> bool {
    link.team(side).home == store.home
}

/// Devices of a local team.
pub async fn team_members(store: &Store, team: &str) -> Vec<String> {
    store.team(team).await.ok().flatten().map(|t| t.members).unwrap_or_default()
}

/// Members of a local team with their names and keys, for other homes.
pub async fn member_list(store: &Store, team: &str) -> Vec<Member> {
    let mut out = Vec::new();
    for d in team_members(store, team).await {
        if let Ok(Some(u)) = store.user(&d).await {
            out.push(Member { device: u.device, name: u.name, dh_pub: u.dh_pub });
        }
    }
    out
}

/// The local side of `link` that `device` belongs to.
pub async fn my_side(store: &Store, link: &LinkDoc, device: &str) -> Option<char> {
    for side in ['a', 'b'] {
        if is_local(store, link, side) && team_members(store, &link.team(side).id).await.iter().any(|d| d == device) {
            return Some(side);
        }
    }
    None
}

/// Local devices on either side of `link`.
pub async fn link_local_devices(store: &Store, link: &LinkDoc) -> Vec<String> {
    let mut out = Vec::new();
    for side in ['a', 'b'] {
        if is_local(store, link, side) {
            out.extend(team_members(store, &link.team(side).id).await);
        }
    }
    out.sort();
    out.dedup();
    out
}

pub fn writable(link: &LinkDoc) -> bool {
    link.state == LinkState::Active
        && link.kind != LinkKind::Personal
        && link.expires_at.is_none_or(|t| t > DateTime::now())
}

pub fn readable(link: &LinkDoc) -> bool {
    writable(link) || (link.state == LinkState::Archived && link.archive_open())
}

fn other_side(side: char) -> char {
    if side == 'a' { 'b' } else { 'a' }
}

/// A conversation as `me` (a local device) uses it.
pub async fn open(store: &Store, conversation: &str, me: &str, access: Access) -> Result<Room, ServerMsg> {
    let room = parse_conversation(conversation).ok_or_else(|| ServerMsg::error("bad_request", "unknown conversation id"))?;
    match room {
        ConvRef::Dm(a, b) => {
            let other = if a == me {
                b.clone()
            } else if b == me {
                a.clone()
            } else {
                return Err(denied("no such conversation"));
            };
            let user = store.user(&other).await.map_err(store_err)?.ok_or_else(|| denied("that person has never connected"))?;
            if user.local {
                return Ok(Room { id: conversation.into(), dm_members: vec![a, b], local: vec![me.into(), other], forward: vec![] });
            }
            // Someone on another home: only through a personal link between our teams.
            for link_id in &user.via {
                let Some(link) = store.link(link_id).await.map_err(store_err)? else { continue };
                if link.kind != LinkKind::Personal || link.state != LinkState::Active {
                    continue;
                }
                let Some(mine) = my_side(store, &link, me).await else { continue };
                if link.team(other_side(mine)).members.iter().any(|m| m.device == other) {
                    return Ok(Room { id: conversation.into(), dm_members: vec![a, b], local: vec![me.into()], forward: vec![link] });
                }
            }
            Err(denied("you can message people from another team only after a personal-chat request is accepted"))
        }
        ConvRef::Team(t) => {
            let members = team_members(store, &t).await;
            if !members.iter().any(|d| d == me) {
                return Err(denied("you are not in that team"));
            }
            Ok(Room { id: conversation.into(), dm_members: vec![], local: members, forward: vec![] })
        }
        ConvRef::Link(l) => {
            let link = store.link(&l).await.map_err(store_err)?.ok_or_else(|| denied("no such group"))?;
            my_side(store, &link, me).await.ok_or_else(|| denied("your team is not in that group"))?;
            let ok = if access == Access::Write { writable(&link) } else { readable(&link) };
            if !ok {
                let why = match link.state {
                    LinkState::Pending => "the other team has not accepted yet",
                    LinkState::Archived => "this temporary group has closed; both teams must release the archive to read it",
                    _ => "this group is closed",
                };
                return Err(ServerMsg::error("closed", why));
            }
            let local = link_local_devices(store, &link).await;
            let forward = if ['a', 'b'].iter().all(|s| is_local(store, &link, *s)) { vec![] } else { vec![link] };
            Ok(Room { id: conversation.into(), dm_members: vec![], local, forward })
        }
    }
}

/// A message another home forwarded for `link`, sent by `from` (one of that
/// home's members) at `created_at`. Returns the room on this side, or None if
/// not allowed. A temporary group's message written before it closed is
/// still kept (it was queued while this home was offline), but not pushed.
pub async fn incoming(store: &Store, conversation: &str, from: &str, created_at: DateTime, link: &LinkDoc) -> Option<Room> {
    let foreign = ['a', 'b'].into_iter().find(|s| !is_local(store, link, *s))?;
    if !link.team(foreign).members.iter().any(|m| m.device == from) {
        return None;
    }
    let local_side = other_side(foreign);
    match parse_conversation(conversation)? {
        ConvRef::Link(l) if l == link.id && link.kind != LinkKind::Personal && link.state == LinkState::Active => {
            Some(Room { id: conversation.into(), dm_members: vec![], local: link_local_devices(store, link).await, forward: vec![] })
        }
        ConvRef::Link(l)
            if l == link.id
                && link.kind == LinkKind::Temp
                && link.state == LinkState::Archived
                && link.expires_at.is_some_and(|t| created_at <= t) =>
        {
            Some(Room { id: conversation.into(), dm_members: vec![], local: vec![], forward: vec![] })
        }
        ConvRef::Dm(a, b) if link.kind == LinkKind::Personal && link.state == LinkState::Active => {
            let other = if a == from { &b } else if b == from { &a } else { return None };
            let locals = team_members(store, &link.team(local_side).id).await;
            locals.iter().any(|d| d == other).then(|| Room {
                id: conversation.into(),
                dm_members: vec![a.clone(), b.clone()],
                local: vec![other.clone()],
                forward: vec![],
            })
        }
        _ => None,
    }
}
