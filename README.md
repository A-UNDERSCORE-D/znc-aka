# znc-aka
A ZNC module to track users

### WARNING Before Upgrading to 2

AKA has been rewritten from the ground up - the module now utilizes a single, user database for all networks and is no longer enabled on a per-network basis. Several features have been removed due to excessive overhead either on the ZNC server or IRC itself. New and retained features are faster and more accurate. Please read all information below, particularly the available commands, before ugrading.

If you agree to this update, please note that on first load, AKA will need to convert all old databases to the new, single user database format. This may take some time, depending on the amount of data you have, and will cause ZNC to freeze up while processing. Please do not quit or restart ZNC until this process is complete, as noted by the module responding to commands and new messages being received on IRC.

## Table of Contents
- [Requirements](#requirements)
- [Installation](#installation)
- [Loading](#loading)
- [Commands](#commands)
- [Contact](#contact)

## Requirements
 * <a href="http://znc.in">ZNC</a>
 * <a href="https://www.python.org">Python 3</a>
 * <a href="http://wiki.znc.in/Modpython">modpython</a>
 * <a href="http://docs.python-requests.org/en/latest/">python3-requests</a>
 * <a href="https://www.sqlite.org">sqlite3</a>

## Installation
To install aka, place aka.py in your ZNC modules folder

## Loading
`/msg *status loadmod aka`

## Commands

`all <user>` Get all information on a user (nick, ident, or host)

`history <user>` Show history for a user (nick, ident, or host)

`channels <user>` Get all channels a user (nick, ident, or host) has been seen in

`sharedchans <user 1> <user 2> ... <user #>` Show common channels between a list of users (nicks, idents, and/or hosts)

`sharedusers <#channel 1> <#channel 2> ... <#channel #>` Show common users between a list of channels

`seen <user> [<#channel>]` Display last time user (nick, ident, or host) was seen speaking

`geo <user>` Geolocates user (nick, ident, host, IP, or domain)

`who <scope>` Update userdata on all users in the scope (#channel, network, or all)

`process <scope>` Add all current users in the scope (#channel, network, or all) to the database

`rawquery <query>` Run raw sqlite3 query and return results

`about` Display information about aka

`stats` Print data stats for the current network

`help` Print help from the module

## Contact

Issues/bugs should be submitted on the <a href="https://github.com/MuffinMedic/znc-aka/issues">GitHub issues page</a>.

For assistance, please PM MuffinMedic (Evan) on <a href="https://kiwiirc.com/client/irc.snoonet.org:+6697">Snoonet<a> or <a href="https://kiwiirc.com/client/irc.freenode.net:+6697">freenode<a/>.