# COPYRIGHT (C) 2020-2021 Nicotine+ Team
# COPYRIGHT (C) 2018 Mutnick <mutnick@techie.com>
# COPYRIGHT (C) 2016-2017 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (C) 2008-2011 Quinox <quinox@users.sf.net>
# COPYRIGHT (C) 2009 Hedonist <ak@sensi.org>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
# COPYRIGHT (C) 2003-2004 Hyriand <hyriand@thegraveyard.org>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from sys import maxsize
from time import time

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from pynicotine.gtkgui.utils import human_size
from pynicotine.gtkgui.utils import human_speed
from pynicotine.gtkgui.utils import initialise_columns
from pynicotine.gtkgui.utils import PopupMenu
from pynicotine.gtkgui.utils import save_columns
from pynicotine.gtkgui.utils import select_user_row_iter
from pynicotine.gtkgui.utils import set_treeview_selected_row
from pynicotine.gtkgui.utils import triggers_context_menu
from pynicotine.gtkgui.utils import update_widget_visuals


class TransferList:

    def __init__(self, frame, widget, type):
        self.frame = frame
        self.widget = widget
        self.type = type
        self.last_ui_update = self.last_save = time()
        self.list = []
        self.users = {}
        self.paths = {}

        # Status list
        self.statuses = {}
        self.statuses["Waiting for download"] = _("Waiting for download")
        self.statuses["Requesting file"] = _("Requesting file")
        self.statuses["Initializing transfer"] = _("Initializing transfer")
        self.statuses["Cannot connect"] = _("Cannot connect")
        self.statuses["Waiting for peer to connect"] = _("Waiting for peer to connect")
        self.statuses["Connecting"] = _("Connecting")
        self.statuses["Getting address"] = _("Getting address")
        self.statuses["Getting status"] = _("Getting status")
        self.statuses["Queued"] = _("Queued")
        self.statuses["User logged off"] = _("User logged off")
        self.statuses["Aborted"] = _("Aborted")
        self.statuses["Finished"] = _("Finished")
        self.statuses["Paused"] = _("Paused")
        self.statuses["Transferring"] = _("Transferring")
        self.statuses["Filtered"] = _("Filtered")
        self.statuses["Connection closed by peer"] = _("Connection closed by peer")
        self.statuses["File not shared"] = _("File not shared")
        self.statuses["File not shared."] = _("File not shared")  # The official client sends a variant containing a dot
        self.statuses["Establishing connection"] = _("Establishing connection")
        self.statuses["Download directory error"] = _("Download directory error")
        self.statuses["Local file error"] = _("Local file error")
        self.statuses["Remote file error"] = _("Remote file error")

        # String templates
        self.extension_list_template = _("All %(ext)s")
        self.files_template = _("%(number)2s files ")

        widget.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        widget.set_enable_tree_lines(True)
        widget.set_rubber_banding(True)

        self.transfersmodel = Gtk.TreeStore(
            str,                   # (0)  user
            str,                   # (1)  path
            str,                   # (2)  file name
            str,                   # (3)  status
            str,                   # (4)  hqueue position
            GObject.TYPE_UINT64,   # (5)  percent
            str,                   # (6)  hsize
            str,                   # (7)  hspeed
            str,                   # (8)  htime elapsed
            str,                   # (9)  time left
            str,                   # (10) path
            str,                   # (11) status (non-translated)
            GObject.TYPE_UINT64,   # (12) size
            GObject.TYPE_UINT64,   # (13) current bytes
            GObject.TYPE_UINT64,   # (14) speed
            GObject.TYPE_UINT64,   # (15) time elapsed
            GObject.TYPE_UINT64,   # (16) file count
            GObject.TYPE_UINT64,   # (17) queue position
        )

        text_color = self.frame.np.config.sections["ui"]["search"]

        self.cols = cols = initialise_columns(
            type,
            widget,
            ["user", _("User"), 200, "text", None, (text_color, None)],
            ["path", _("Path"), 400, "text", None, (text_color, None)],
            ["filename", _("Filename"), 400, "text", None, (text_color, None)],
            ["status", _("Status"), 140, "text", None, (text_color, None)],
            ["queue_position", _("Queue Position"), 50, "number", None, (text_color, None)],
            ["percent", _("Percent"), 70, "progress", None, None],
            ["size", _("Size"), 170, "number", None, (text_color, None)],
            ["speed", _("Speed"), 90, "number", None, (text_color, None)],
            ["time_elapsed", _("Time Elapsed"), 140, "number", None, (text_color, None)],
            ["time_left", _("Time Left"), 0, "number", None, (text_color, None)],
        )

        cols["user"].set_sort_column_id(0)
        cols["path"].set_sort_column_id(1)
        cols["filename"].set_sort_column_id(2)
        cols["status"].set_sort_column_id(11)
        cols["queue_position"].set_sort_column_id(17)
        cols["percent"].set_sort_column_id(5)
        cols["size"].set_sort_column_id(12)
        cols["speed"].set_sort_column_id(14)
        cols["time_elapsed"].set_sort_column_id(8)
        cols["time_left"].set_sort_column_id(9)

        widget.set_model(self.transfersmodel)

        widget.connect("button_press_event", self.on_list_clicked)
        widget.connect("popup_menu", self.on_popup_menu)
        widget.connect("touch_event", self.on_list_clicked)
        widget.connect("key-press-event", self.on_key_press_event)

        self.update_visuals()

    def save_columns(self):
        save_columns(self.type, self.widget.get_columns())

    def update_visuals(self):

        for widget in self.__dict__.values():
            update_widget_visuals(widget, list_font_target="transfersfont")

    def init_interface(self, list):
        self.list = list
        self.update()
        self.widget.set_sensitive(True)

    def conn_close(self):
        self.widget.set_sensitive(False)
        self.list = []
        self.clear()

    def select_transfers(self):
        self.selected_transfers = set()
        self.selected_users = set()

        self.widget.get_selection().selected_foreach(self.selected_transfers_callback)

    def new_transfer_notification(self):
        self.frame.request_tab_icon(self.tab_label)

    def on_ban(self, widget):
        self.select_transfers()

        for user in self.selected_users:
            self.frame.ban_user(user)

    def on_file_search(self, widget):

        for transfer in self.selected_transfers:
            self.frame.SearchEntry.set_text(transfer.filename.rsplit("\\", 1)[1])
            self.frame.change_main_page("search")
            break

    def rebuild_transfers(self):
        if self.frame.np.transfers is None:
            return

        self.clear()
        self.update()

    def selected_transfers_callback(self, model, path, iterator):

        self.select_transfer(model, iterator, selectuser=True)

        # If we're in grouping mode, select any transfers under the selected
        # user or folder
        self.select_child_transfers(model, model.iter_children(iterator))

    def select_child_transfers(self, model, iterator):

        while iterator is not None:
            self.select_transfer(model, iterator)
            self.select_child_transfers(model, model.iter_children(iterator))
            iterator = model.iter_next(iterator)

    def select_transfer(self, model, iterator, selectuser=False):
        user = model.get_value(iterator, 0)
        file = model.get_value(iterator, 10)

        for i in self.list:
            if i.user == user and i.filename == file:
                self.selected_transfers.add(i)
                break

        if selectuser:
            self.selected_users.add(user)

    def translate_status(self, status):

        try:
            newstatus = self.statuses[status]
        except KeyError:
            newstatus = status

        return newstatus

    def update(self, transfer=None, forceupdate=False):

        curtime = time()

        if (curtime - self.last_save) > 15:

            """ Save downloads list to file every 15 seconds """

            if self.frame.np.transfers is not None:
                self.frame.np.transfers.save_downloads()

            self.last_save = curtime

        if not forceupdate:
            if self.frame.current_tab_label != self.tab_label:
                """ No need to do unnecessary work if transfers are not visible """
                return

        if transfer is not None:
            self.update_specific(transfer)
        elif self.list is not None:

            for i in self.list:
                self.update_specific(i)

        finished = (transfer is not None and transfer.status == "Finished")

        if not forceupdate and \
            not finished and \
                (curtime - self.last_ui_update) <= 1:

            """ Unless a transfer finishes, use a cooldown to avoid updating
            too often """

            return

        self.update_parent_rows()

    def update_parent_rows(self, only_remove=False):

        # Remove empty parent rows
        for (path, pathiter) in list(self.paths.items()):
            if not self.transfersmodel.iter_has_child(pathiter):
                self.transfersmodel.remove(pathiter)
                del self.paths[path]
            elif not only_remove:
                self.update_parent_row(pathiter)

        for (username, useriter) in list(self.users.items()):
            if useriter != 0:
                if not self.transfersmodel.iter_has_child(useriter):
                    self.transfersmodel.remove(useriter)
                    del self.users[username]
                elif not only_remove:
                    self.update_parent_row(useriter)
            else:
                # No grouping

                for transfer in self.list:
                    if transfer.user == username:
                        break
                else:
                    del self.users[username]

        self.frame.update_bandwidth()
        self.last_ui_update = time()

    def update_parent_row(self, initer):

        speed = 0.0
        percent = totalsize = position = 0
        hspeed = helapsed = left = ""
        elapsed = 0
        filecount = 0
        salientstatus = ""
        extensions = {}

        iterator = self.transfersmodel.iter_children(initer)

        while iterator is not None:

            status = self.transfersmodel.get_value(iterator, 11)

            if salientstatus in ('', "Finished", "Filtered"):  # we prefer anything over ''/finished
                salientstatus = status

            filename = self.transfersmodel.get_value(iterator, 10)
            parts = filename.rsplit('.', 1)

            if len(parts) == 2:
                ext = parts[1]
                try:
                    extensions[ext.lower()] += 1
                except KeyError:
                    extensions[ext.lower()] = 1

            if status == "Filtered":
                # We don't want to count filtered files when calculating the progress
                iterator = self.transfersmodel.iter_next(iterator)
                continue

            elapsed += self.transfersmodel.get_value(iterator, 15)
            totalsize += self.transfersmodel.get_value(iterator, 12)
            position += self.transfersmodel.get_value(iterator, 13)
            filecount += self.transfersmodel.get_value(iterator, 16)

            if status == "Transferring":
                speed += float(self.transfersmodel.get_value(iterator, 14))
                left = self.transfersmodel.get_value(iterator, 9)

            if status in ("Transferring", "Banned", "Getting address", "Establishing connection"):
                salientstatus = status

            iterator = self.transfersmodel.iter_next(iterator)

        if totalsize > 0:
            percent = min(((100 * position) / totalsize), 100)
        else:
            percent = 100

        if speed > 0:
            hspeed = human_speed(speed)
            left = self.frame.np.transfers.get_time((totalsize - position) / speed)

        if elapsed > 0:
            helapsed = self.frame.np.transfers.get_time(elapsed)

        if len(extensions) == 0:
            extensions = ""
        elif len(extensions) == 1:
            extensions = " (" + self.extension_list_template % {'ext': list(extensions.keys())[0]} + ")"
        else:
            extensionlst = [(extensions[key], key) for key in extensions]
            extensionlst.sort(reverse=True)
            extensions = " (" + ", ".join([str(count) + " " + ext for (count, ext) in extensionlst]) + ")"

        self.transfersmodel.set(
            initer,
            2, self.files_template % {'number': filecount} + extensions,
            3, self.translate_status(salientstatus),
            5, percent,
            6, "%s / %s" % (human_size(position), human_size(totalsize)),
            7, hspeed,
            8, helapsed,
            9, left,
            11, salientstatus,
            12, totalsize,
            13, position,
            14, speed,
            15, elapsed,
            16, filecount,
        )

    def update_specific(self, transfer=None):

        currentbytes = transfer.currentbytes
        place = transfer.place

        hspeed = helapsed = ""

        if currentbytes is None:
            currentbytes = 0

        status = transfer.status
        hstatus = self.translate_status(status)

        try:
            size = int(transfer.size)
            if size < 0 or size > maxsize:
                size = 0
        except TypeError:
            size = 0

        hsize = "%s / %s" % (human_size(currentbytes), human_size(size))

        if transfer.modifier:
            hsize += " (%s)" % transfer.modifier

        speed = transfer.speed or 0
        elapsed = transfer.timeelapsed or 0
        left = transfer.timeleft

        if speed > 0:
            speed = float(speed)
            hspeed = human_speed(speed)

        if elapsed > 0:
            helapsed = self.frame.np.transfers.get_time(elapsed)

        try:
            icurrentbytes = int(currentbytes)
            percent = min(((100 * icurrentbytes) / int(size)), 100)

        except Exception:
            icurrentbytes = 0
            percent = 100

        # Modify old transfer
        if transfer.iter is not None:
            self.transfersmodel.set(
                transfer.iter,
                3, hstatus,
                4, str(place),
                5, percent,
                6, str(hsize),
                7, hspeed,
                8, helapsed,
                9, left,
                11, status,
                12, size,
                13, currentbytes,
                14, speed,
                15, elapsed,
                17, place
            )
        else:
            fn = transfer.filename
            user = transfer.user
            shortfn = fn.split("\\")[-1]
            filecount = 1

            if self.tree_users != "ungrouped":
                # Group by folder or user

                if user not in self.users:
                    # Create Parent if it doesn't exist
                    # ProgressRender not visible (last column sets 4th column)
                    self.users[user] = self.transfersmodel.append(
                        None,
                        [user, "", "", "", "", 0, "", "", "", "", "", "", 0, 0, 0, 0, filecount, 0]
                    )

                parent = self.users[user]

                if self.tree_users == "folder_grouping":
                    # Group by folder

                    """ Paths can be empty if files are downloaded individually, make sure we
                    don't add files to the wrong user in the TreeView """
                    path = transfer.path
                    user_path = user + path
                    reverse_path = '/'.join(reversed(path.split('/')))

                    if user_path not in self.paths:
                        self.paths[user_path] = self.transfersmodel.append(
                            self.users[user],
                            [user, reverse_path, "", "", "", 0, "", "", "", "", "", "", 0, 0, 0, 0, filecount, 0]
                        )

                    parent = self.paths[user_path]
            else:
                # No grouping

                if user not in self.users:
                    # Insert dummy value. We use this list to get the total number of users
                    self.users[user] = 0

                parent = None

            # Add a new transfer
            if self.tree_users == "folder_grouping":
                # Group by folder, path not visible
                path = None
            else:
                path = '/'.join(reversed(transfer.path.split('/')))

            iterator = self.transfersmodel.append(
                parent,
                (user, path, shortfn, status, str(place), percent, str(hsize), hspeed, helapsed, left, fn, transfer.status, size, icurrentbytes, speed, elapsed, filecount, place)
            )
            transfer.iter = iterator

            # Expand path
            if parent is not None:
                transfer_path = self.transfersmodel.get_path(iterator)

                if self.tree_users == "folder_grouping":
                    # Group by folder, we need the user path to expand it

                    user_path = self.transfersmodel.get_path(self.users[user])
                else:
                    user_path = None

                self.expand(transfer_path, user_path)

    def abort_transfers(self, remove_file=False, clear=False):

        for i in self.selected_transfers:
            if i.status != "Finished":
                self.frame.np.transfers.abort_transfer(i, remove_file)

                if not clear:
                    i.status = "Aborted"
                    self.update(i)

            if clear:
                self.remove_specific(i)

    def remove_specific(self, transfer, cleartreeviewonly=False):

        if not cleartreeviewonly:
            self.list.remove(transfer)

        if transfer.iter is not None:
            self.transfersmodel.remove(transfer.iter)

        self.update_parent_rows(only_remove=True)

    def clear_transfers(self, status):

        for i in self.list[:]:
            if i.status in status:
                if i.transfertimer is not None:
                    i.transfertimer.cancel()

                if i.status == "Queued":
                    self.frame.np.transfers.abort_transfer(i)

                self.remove_specific(i)

    def clear(self):

        self.users.clear()
        self.paths.clear()
        self.selected_transfers = set()
        self.selected_users = set()
        self.transfersmodel.clear()

        if self.list is not None:
            for i in self.list:
                i.iter = None

    def on_list_clicked(self, widget, event):

        if triggers_context_menu(event):
            set_treeview_selected_row(widget, event)
            return self.on_popup_menu(widget)

        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            self.double_click(event)
            return True

        return False

    def on_popup_menu_users(self, widget):

        self.popup_menu_users.clear()

        if len(self.selected_users) > 0:

            items = []

            for user in self.selected_users:

                popup = PopupMenu(self.frame, False)
                popup.setup_user_menu(user)
                popup.append_item(("", None))
                popup.append_item(("#" + _("Select User's Transfers"), self.on_select_user_transfers))

                items.append((1, user, popup, self.on_popup_menu_user, popup))

            self.popup_menu_users.setup(*items)

        return True

    def on_popup_menu_user(self, widget, popup=None):

        if popup is None:
            return

        popup.toggle_user_items()
        return True

    def on_select_user_transfers(self, widget):

        if len(self.selected_users) == 0:
            return

        selected_user = widget.get_parent().user

        sel = self.widget.get_selection()
        fmodel = self.widget.get_model()
        sel.unselect_all()

        iterator = fmodel.get_iter_first()

        select_user_row_iter(fmodel, sel, 0, selected_user, iterator)

        self.select_transfers()

    def on_copy_file_path(self, widget):

        if not self.selected_transfers:
            return

        i = next(iter(self.selected_transfers))
        text = self.transfersmodel.get_value(i.iter, 10)

        self.frame.clip.set_text(text, -1)

    def on_copy_url(self, widget):
        i = next(iter(self.selected_transfers))
        self.frame.set_clipboard_url(i.user, i.filename)

    def on_copy_dir_url(self, widget):

        i = next(iter(self.selected_transfers))
        path = "\\".join(i.filename.split("\\")[:-1])

        if path[:-1] != "/":
            path += "/"

        self.frame.set_clipboard_url(i.user, path)

    def on_clear_transfer(self, widget):
        self.select_transfers()
        self.abort_transfers(remove_file=False, clear=True)

    def on_clear_response(self, dialog, response, data=None):
        if response == Gtk.ResponseType.OK:
            self.clear_transfers(["Queued"])

        dialog.destroy()

    def on_clear_finished(self, widget):
        self.clear_transfers(["Finished"])

    def on_clear_aborted(self, widget):
        self.clear_transfers(["Aborted", "Cancelled"])

    def on_clear_filtered(self, widget):
        self.clear_transfers(["Filtered"])

    def on_clear_paused(self, widget):
        self.clear_transfers(["Paused"])

    def on_clear_finished_aborted(self, widget):
        self.clear_transfers(["Aborted", "Cancelled", "Finished", "Filtered"])

    def on_clear_finished_erred(self, widget):
        self.clear_transfers(["Aborted", "Cancelled", "Finished", "Filtered", "Cannot connect", "Connection closed by peer", "Local file error", "Remote file error"])
