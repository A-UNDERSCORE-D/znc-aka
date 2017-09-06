#  znc-aka: A ZNC module to track users
#  Copyright (C) 2016 Evan Magaliff
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program; if not, write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#  Authors: Evan (MuffinMedic), Aww (AwwCookies)                          #
#  Contributors: See CHANGELOG for specific contributions by users        #
#  Desc: A ZNC module to track users                                      #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

version = '2.0.3.1'
updated = "October 20, 2016"

import znc
import os
import datetime
import time
import re
import sqlite3
import requests

class aka(znc.Module):
    module_types = [znc.CModInfo.UserModule]
    description = "Tracks users, allowing tracing and history viewing of nicks, hosts, and channels"
    wiki_page = "aka"

    def OnLoad(self, args, message):

        self.USER = self.GetUser().GetUserName()

        self.db_setup()

        self.chan_reg = re.compile('(#\S+)')

        return True

    def OnJoin(self, user, channel):
        self.process_user(self.GetNetwork().GetName(), user.GetNick(), user.GetIdent(), user.GetHost(), channel.GetName())

    def OnNick(self, user, new_nick, channels):
        for chan in channels:
            self.process_user(self.GetNetwork().GetName(), new_nick, user.GetIdent(), user.GetHost(), chan.GetName())

    def OnPrivMsg(self, user, message):
        self.process_seen(self.GetNetwork().GetName(), user.GetNick(), user.GetIdent(), user.GetHost(), 'PRIVMSG', message)

    def OnChanMsg(self, user, channel, message):
        self.process_seen(self.GetNetwork().GetName(), user.GetNick(), user.GetIdent(), user.GetHost(), channel.GetName(), message)

    def OnChanAction(self, user, channel, message):
        message = "* " + str(message).replace("'","''")
        self.process_seen(self.GetNetwork().GetName(), user.GetNick(), user.GetIdent(), user.GetHost(), channel.GetName(), message)

    def OnUserJoin(self, channel, key):
        self.PutIRC("WHO %s" % channel)

    def process_user(self, network, nick, ident, host, channel):
        self.cur.execute("INSERT OR IGNORE INTO users (network, nick, ident, host, channel, time) VALUES (?, ?, ?, ?, ?, strftime('%s', 'now'));", (network.lower(), nick.lower(), ident.lower(), host.lower(), channel.lower()))
        self.conn.commit()

    def process_seen(self, network, nick, ident, host, channel, message):
        message = str(message).replace("'","''")
        self.cur.execute("INSERT OR REPLACE INTO users (network, nick, ident, host, channel, message, time) VALUES (?, ?, ?, ?, ?, ?, strftime('%s', 'now'));", (network.lower(), nick.lower(), ident.lower(), host.lower(), channel.lower(), message))
        self.conn.commit()

    def cmd_process(self, scope):
        self.PutModule("Processing {}.".format(scope))
        if scope == 'all':
            nets = self.GetUser().GetNetworks()
            for net in nets:
                chans = net.GetChans()
                for chan in chans:
                    nicks = chan.GetNicks()
                    for nick in nicks.items():
                        self.process_user(net.GetName(), nick[1].GetNick(), nick[1].GetIdent(), nick[1].GetHost(), chan.GetName())
        elif scope == 'network':
            chans = self.GetNetwork().GetChans()
            for chan in chans:
                nicks = chan.GetNicks()
                for nick in nicks.items():
                    self.process_user(self.GetNetwork().GetName(), nick[1].GetNick(), nick[1].GetIdent(), nick[1].GetHost(), chan.GetName())
        else:
            nicks = self.GetNetwork().FindChan(scope).GetNicks()
            for nick in nicks.items():
                self.process_user(self.GetNetwork().GetName(), nick[1].GetNick(), nick[1].GetIdent(), nick[1].GetHost(), scope)
        self.PutModule("{} processed.".format(scope))

    def cmd_history(self, user):
        self.PutModule("Looking up \x02history\x02 for \x02{}\x02, please be patient...".format(user.lower()))
        self.cur.execute("SELECT DISTINCT nick, host FROM users WHERE network = '{0}' AND (nick GLOB '{1}' OR ident GLOB '{1}' OR host GLOB '{1}');".format(self.GetNetwork().GetName().lower(), user.lower()))
        data = self.cur.fetchall()
        nicks, idents, hosts = set(), set(), set()
        if len(data) > 0:
            for row in data:
                nicks.add("nick = '" + row[0] + "' OR")
                hosts.add("host = '" + row[1] + "' OR")

            self.cur.execute("SELECT DISTINCT nick, ident, host FROM users WHERE network = '{}' AND ({} {})".format(self.GetNetwork().GetName().lower(), ' '.join(nicks), ' '.join(hosts)[:-3]))
            data = self.cur.fetchall()
            nicks.clear()
            hosts.clear()
            for row in data:
                nicks.add(row[0])
                idents.add(row[1])
                hosts.add(row[2])

            self.display_results(nicks, idents, hosts)
            self.PutModule("History for {} \x02complete\x02.".format(user.lower()))
        else:
            self.PutModule("No history found for \x02{}\x02".format(user.lower()))

    def display_results(self, nicks, idents, hosts):
        nicks, idents, hosts = sorted(list(nicks)), sorted(list(idents)), sorted(list(hosts))
        size = 100
        index = 0
        while index < len(nicks):
            self.PutModule("\x02Nick(s):\x02 " + ', '.join(nicks[index:index+size]))
            index += size
        index = 0
        while index < len(idents):
            self.PutModule("\x02Ident(s):\x02 " + ', '.join(idents[index:index+size]))
            index += size
        index = 0
        while index < len(hosts):
            self.PutModule("\x02Host(s):\x02 " + ', '.join(hosts[index:index+size]))
            index += size

    def cmd_seen(self, user, channel):
        if channel:
            self.cur.execute("SELECT nick, ident, host, channel, message, MAX(time) FROM (SELECT * from users WHERE message IS NOT NULL) WHERE network = '{0}' AND channel = '{1}' AND (nick GLOB '{2}' OR ident GLOB '{2}' OR host GLOB '{2}');".format(self.GetNetwork().GetName().lower(), channel.lower(), user.lower()))
        else:
            self.cur.execute("SELECT nick, ident, host, channel, message, MAX(time) FROM (SELECT * from users WHERE message IS NOT NULL) WHERE network = '{0}' AND (nick GLOB '{1}' OR ident GLOB '{1}' OR host GLOB '{1}');".format(self.GetNetwork().GetName().lower(), user.lower()))
        data = self.cur.fetchone()

        if len(data) >= 6:
            self.PutModule("\x02{}\x02 ({}@{}) was last seen in \x02{}\x02 at \x02{}\x02 saying \"\x02{}\x02\".".format(data[0], data[1], data[2],data[3], datetime.datetime.fromtimestamp(int(data[5])).strftime('%Y-%m-%d %H:%M:%S'), data[4]))
        else:
            if channel:
                self.PutModule("\x02{}\x02 has \x02\x034not\x03\x02 been seen in \x02{}\x02.".format(user.lower(), channel.lower()))
            else:
                self.PutModule("\x02{}\x02 has \x02\x034not\x03\x02 been seen.".format(user.lower()))

    def cmd_users(self, user):
        self.cur.execute("SELECT DISTINCT nick, host, ident FROM users WHERE network = '{0}' AND (nick GLOB '{1}' OR ident GLOB '{1}' OR host GLOB '{1}');".format(self.GetNetwork().GetName().lower(), user.lower()))
        data = self.cur.fetchall()
        chans = set()
        for row in data:
            chans.add(row[0])
        self.PutModule("\x02{}\x02 has been seen in \x02channels\x02: {}".format(user.lower(), ', '.join(sorted(chans))))

    def cmd_channels(self, users):
        chan_lists = []
        for user in users:
            chans = []
            self.cur.execute("SELECT DISTINCT channel FROM users WHERE network = '{0}' AND (nick GLOB '{1}' OR ident GLOB '{1}' OR host GLOB '{1}');".format(self.GetNetwork().GetName().lower(), user.lower()))
            data = self.cur.fetchall()
            for row in data:
                chans.append(row[0])
            chan_lists.append(chans)
        shared_chans = set(chan_lists[0])
        for chan in chan_lists[1:]:
            shared_chans.intersection_update(chan)
        self.PutModule("Common \x02channels\x02 for \x02{}:\x02 {}".format(', '.join(users), ', '.join(sorted(shared_chans))))

    def cmd_users(self, channels):
        nick_lists, ident_lists, host_lists = [], [], []
        for channel in channels:
            nicks, idents, hosts = [], [], []
            self.cur.execute("SELECT DISTINCT nick, ident, host FROM users WHERE network = '{}' AND channel = '{}';".format(self.GetNetwork().GetName().lower(), channel.lower()))
            data = self.cur.fetchall()
            for row in data:
                nicks.append(row[0])
                idents.append(row[1])
                hosts.append(row[2])

            nick_lists.append(nicks)
            ident_lists.append(idents)
            host_lists.append(hosts)

        shared_nicks, shared_idents, shared_hosts = set(nick_lists[0]), set(ident_lists[0]), set(host_lists[0])
        for nick in nick_lists[1:]:
            shared_nicks.intersection_update(nick)
        for ident in ident_lists[1:]:
            shared_idents.intersection_update(ident)
        for host in host_lists[1:]:
            shared_hosts.intersection_update(host)
        self.PutModule("Common \x02nicks\x02 for \x02{}:\x02 {}".format(', '.join(channels), ', '.join(sorted(shared_nicks))))
        self.PutModule("Common \x02idents\x02 for \x02{}:\x02 {}".format(', '.join(channels), ', '.join(sorted(shared_idents))))
        self.PutModule("Common \x02hosts\x02 for \x02{}:\x02 {}".format(', '.join(channels), ', '.join(sorted(shared_hosts))))

    def cmd_compare_users(self, users):
        self.PutModule("Users compared.")

    def cmd_geo(self, user):
        ipv4 = '(?:[0-9]{1,3}(\.|\-)){3}[0-9]{1,3}'
        ipv6 = '^((?:[0-9A-Fa-f]{1,4}))((?::[0-9A-Fa-f]{1,4}))*::((?:[0-9A-Fa-f]{1,4}))((?::[0-9A-Fa-f]{1,4}))*|((?:[0-9A-Fa-f]{1,4}))((?::[0-9A-Fa-f]{1,4})){7}$'
        rdns = '^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$'
        
        if (re.search(ipv6, str(user)) or re.search(ipv4, str(user)) or (re.search(rdns, str(user)) and '.' in str(user))):
            host = user

        self.cur.execute("SELECT host, nick, ident FROM users WHERE network = '{0}' AND (nick GLOB '{1}' OR ident GLOB '{1}' OR host GLOB '{1}') ORDER BY time DESC;".format(self.GetNetwork().GetName().lower(), user.lower()))
        data = self.cur.fetchall()
        for row in data:
            if (re.search(ipv6, str(row[0])) or re.search(ipv4, str(row[0])) or (re.search(rdns, str(row[0])) and '.' in str(row[0]))):
                host = row[0]
                nick = row[1]
                ident = row[2]
                break
        try:
            if re.search(ipv4, str(host)):
                ip = re.sub('[^\w.]',".",((re.search(ipv4, str(host))).group(0)))
            elif re.search(ipv6, str(host)) or re.search(rdns, str(host)):
                ip = str(host)
            url = 'http://ip-api.com/json/' + ip + '?fields=country,regionName,city,lat,lon,timezone,mobile,proxy,query,reverse,status,message'
            loc = requests.get(url)
            loc_json = loc.json()

            if loc_json["status"] != "fail":
                try:
                    user = "\x02{}\x02 ({}@{})".format(nick.lower(), ident.lower(), host.lower()) 
                except:
                    user = "\x02{}\x02 (no matching user)".format(user.lower())
                self.PutModule("{} is located in \x02{}, {}, {}\x02 ({}, {}) / Timezone: {} / Proxy: {} / Mobile: {} / IP: {} / rDNS: {}".format(user, loc_json["city"], loc_json["regionName"], loc_json["country"], loc_json["lat"], loc_json["lon"], loc_json["timezone"], loc_json["proxy"], loc_json["mobile"], loc_json["query"], loc_json["reverse"]))
            else:
                self.PutModule("\x02\x034Unable to geolocate\x03\x02 user \x02{}\x02. (Reason: {})".format(user.lower(), loc_json["message"]))
        except:
            self.PutModule("\x02\x034No valid host\x03\x02 for user \x02{}\x02".format(user.lower()))

    def cmd_stats(self):
        self.cur.execute("SELECT COUNT(DISTINCT nick), COUNT(DISTINCT ident), COUNT(DISTINCT host), COUNT(DISTINCT channel), COUNT(*) FROM users WHERE network = '{0}';".format(self.GetNetwork().GetName().lower()))
        for row in self.cur:
            self.PutModule("\x02Nick(s):\x02 {}".format(row[0]))
            self.PutModule("\x02Ident(s):\x02 {}".format(row[1]))
            self.PutModule("\x02Host(s):\x02 {}".format(row[2]))
            self.PutModule("\x02Channel(s):\x02 {}".format(row[3]))
            self.PutModule("\x02Total Records:\x02 {}".format(row[4]))

    def cmd_who(self, scope):
        if scope == 'all':
            nets = self.GetUser().GetNetworks()
            for net in nets:
                chans = net.GetChans()
                for chan in chans:
                    self.PutIRC("WHO %s" % chan.GetName())
        elif scope == 'network':
            chans = self.GetNetwork().GetChans()
            for chan in chans:
                self.PutIRC("WHO %s" % chan.GetName())
        else:
           self.PutIRC("WHO %s" % scope)
        self.PutModule("{} WHO updates triggered. Please wait several minutes for ZNC to receive the updated data from the IRC server(s) and then run \x02process\x02 to add these updates to the database".format(scope))

    def cmd_about(self):
        self.PutModule("\x02aka\x02 (Also Known As / nickhistory) ZNC module by MuffinMedic (Evan)")
        self.PutModule("\x02Description:\x02 {}".format(self.description))
        self.PutModule("\x02Version:\x02 {}".format(version))
        self.PutModule("\x02Updated:\x02 {}".format(updated))
        self.PutModule("\x02Documenation:\x02 http://wiki.znc.in/Aka")
        self.PutModule("\x02Source:\x02 https://github.com/MuffinMedic/znc-aka")

    def cmd_rawquery(self, query):
        try:
            query = ' '.join(query)
            count = 0
            for row in self.cur.execute(query):
                self.PutModule(str(row))
                count += 1
            self.conn.commit()
            if self.cur.rowcount >= 0:
                self.PutModule('Query successful: %s rows affected' % self.cur.rowcount)
            else:
                self.PutModule('%s records retrieved' % count)
        except sqlite3.Error as e:
            self.PutModule('Error: %s' % e)

    def db_setup(self):
        self.conn = sqlite3.connect(self.GetSavePath() + "/aka.db")
        self.cur = self.conn.cursor()
        self.cur.execute("create table if not exists users (id INTEGER PRIMARY KEY, network TEXT, nick TEXT, ident TEXT, host TEXT, channel TEXT, message TEXT, time INTEGER, UNIQUE(network, nick, ident, host, channel));")
        self.conn.commit()

        if 'HAS_RUN' not in self.nv:
            self.migrate()
            self.SetNV('HAS_RUN', "TRUE")

    def migrate(self):
        nets = self.GetUser().GetNetworks()
        for net in nets:
            path = self.GetUser().GetUserPath() + "/networks/" + net.GetName() + "/moddata/aka/aka." + net.GetName() + ".db"
            if os.path.exists(path):
                self.old_conn = sqlite3.connect(path)
                self.old_c = self.old_conn.cursor()
                self.old_c.execute("SELECT nick, identity, host, channel, message, processed_time, added FROM users")
                data = self.old_c.fetchall()
                for row in data:
                    if row[5]:
                        self.cur.execute("INSERT OR IGNORE INTO users (network, nick, ident, host, channel, message, time) VALUES (LOWER(?), LOWER(?), LOWER(?), LOWER(?), LOWER(?), LOWER(?), LOWER(?));", (net.GetName(), row[0], row[1], row[2], row[3], row[4], str(time.mktime((datetime.datetime.strptime(row[5].partition('.')[0], '%Y-%m-%d %H:%M:%S')).timetuple())).partition('.')[0]))
                    elif row[6]:
                        self.cur.execute("INSERT OR IGNORE INTO users (network, nick, ident, host, channel, message, time) VALUES (LOWER(?), LOWER(?), LOWER(?), LOWER(?), LOWER(?), LOWER(?), LOWER(?);", (net.GetName(), row[0], row[1], row[2], row[3], row[4], str(time.mktime((datetime.datetime.strptime(row[6].partition('.')[0], '%Y-%m-%d %H:%M:%S')).timetuple())).partition('.')[0]))
                    else:
                        self.cur.execute("INSERT OR IGNORE INTO users (network, nick, ident, host, channel, message) VALUES (LOWER(?), LOWER(?), LOWER(?), LOWER(?), LOWER(?), LOWER(?));", (net.GetName(), row[0], row[1], row[2], row[3], row[4]))
                self.conn.commit()
                os.rename(path, self.GetUser().GetUserPath() + "/networks/" + net.GetName() + "/moddata/aka/aka." + net.GetName() + ".db.old")

    def OnModCommand(self, command):
        command = command.lower()
        # cmds = ["all", "history", "users", "channels", "sharedchans", "sharedusers", "seen", "geo", "process",
        # "who", "rawquery", "stats", "about", "help", "migrate"]

        split_command = command.split()
        top_command = split_command[0]
        if top_command == "all":
            if len(split_command) >= 2:
                self.PutModule("Getting \x02all\x02 for \x02{}\x02.".format(split_command[1]))
                self.cmd_history(split_command[1])
                self.cmd_channels(split_command[1:])
                self.cmd_seen(split_command[1], None)
                self.cmd_geo(split_command[1])
                self.PutModule("All \x02complete\x02.")
            else:
                self.PutModule("You must specify a user.")
        elif top_command == "history":
            if len(split_command) >= 2:
                self.cmd_history(split_command[1])
            else:
                self.PutModule("You must specify a user.")
        elif top_command == "users" or top_command == "channels" or top_command == "sharedchans" or top_command == "sharedusers":
                if top_command == 'channels' or top_command == 'sharedchans':
                    if len(split_command) >= 2:
                        self.cmd_channels(split_command[1:])
                    else:
                        self.PutModule("You must specify at least one user.")
                elif top_command == 'users' or top_command == 'sharedusers':
                    if len(split_command) >= 2:
                        self.cmd_users(split_command[1:])
                    else:
                        self.PutModule("You must specify at least one channel.")
        elif top_command == "seen":
            if len(split_command) >= 2:
                if len(split_command) >= 3:
                    self.cmd_seen(split_command[1], split_command[2])
                else:
                    self.cmd_seen(split_command[1], None)
            else:
                self.PutModule("You must specify a user and optional channel.")
        elif top_command == "geo":
            if len(split_command) >= 2:
                self.cmd_geo(split_command[1])
            else:
                self.PutModule("You must specify a user.")
        elif top_command == "process" or top_command == "who":
            if len(split_command) >= 2:
                if top_command == "process":
                    self.cmd_process(split_command[1])
                elif top_command == "who":
                    self.cmd_who(split_command[1])
            else:
                self.PutModule("Valid options: #channel, network, all")
        elif top_command == "rawquery":
            if len(split_command) >= 2:
                self.cmd_rawquery(split_command[1:])
            else:
                self.PutModule("You must specify a query.")
        elif top_command == "stats":
            self.cmd_stats()
        elif top_command == "about":
            self.cmd_about()
        elif top_command == "help":
            self.cmd_help()
        else:
            self.PutModule("Invalid command. See \x02help\x02 for a list of available commands.")

    def cmd_help(self):
        help_table = znc.CTable(250)
        help_table.AddColumn("Command")
        help_table.AddColumn("Arguments")
        help_table.AddColumn("Description")
        help_table.AddRow()
        help_table.SetCell("Command", "all")
        help_table.SetCell("Arguments", "<user>")
        help_table.SetCell("Description", "Get all information on a user (nick, ident, or host)")
        help_table.AddRow()
        help_table.SetCell("Command", "history")
        help_table.SetCell("Arguments", "<user>")
        help_table.SetCell("Description", "Show history for a user")
        help_table.AddRow()
        help_table.SetCell("Command", "users")
        help_table.SetCell("Arguments", "<#channel 1> [<#channel 2>] ... [<channel #>]")
        help_table.SetCell("Description", "Show common users between a list of channel(s)")
        help_table.AddRow()
        help_table.SetCell("Command", "channels")
        help_table.SetCell("Arguments", "<user 1> [<user 2>] ... [<user #>]")
        help_table.SetCell("Description", "Show common channels between a list of user(s) (nicks, idents, or hosts, including mixed)")
        help_table.AddRow()
        help_table.SetCell("Command", "seen")
        help_table.SetCell("Arguments", "<user> [<#channel>]")
        help_table.SetCell("Description", "Display last time user was seen speaking")
        help_table.AddRow()
        help_table.SetCell("Command", "geo")
        help_table.SetCell("Arguments", "<user>")
        help_table.SetCell("Description", "Geolocates user (nick, ident, host, IP, or domain)")
        help_table.AddRow()
        help_table.SetCell("Command", "who")
        help_table.SetCell("Arguments", "<scope>")
        help_table.SetCell("Description", "Update userdata on all users in the scope (#channel, network, or all)")
        help_table.AddRow()
        help_table.SetCell("Command", "process")
        help_table.SetCell("Arguments", "<scope>")
        help_table.SetCell("Description", "Add all current users in the scope (#channel, network, or all) to the database")
        help_table.AddRow()
        help_table.SetCell("Command", "rawquery")
        help_table.SetCell("Arguments", "<query>")
        help_table.SetCell("Description", "Run raw sqlite3 query and return results")
        help_table.AddRow()
        help_table.SetCell("Command", "about")
        help_table.SetCell("Description", "Display information about aka")
        help_table.AddRow()
        help_table.SetCell("Command", "stats")
        help_table.SetCell("Description", "Print data stats for the current network")
        help_table.AddRow()
        help_table.SetCell("Command", "help")
        help_table.SetCell("Description", "Print help for using the module")
        help_table.AddRow()
        help_table.SetCell("Command", "NOTE")
        help_table.SetCell("Arguments", "Wildcard Searches")
        help_table.SetCell("Description", "<user> supports * and ? GLOB wildcard syntax (combinable at start, middle, and end).")

        self.PutModule(help_table)