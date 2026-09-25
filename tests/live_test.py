#!/usr/bin/env python3
"""Integration test against the desklet running in your Cinnamon session.

It changes settings exactly like the settings dialog does (write the config
file, then call org.Cinnamon.updateSetting), inspects the live widgets through
org.Cinnamon.Eval, and restores your settings, position and active workspace
at the end, even if a check fails.

Requires: the desklet added to the desktop, python3-gi.
Usage:    tests/live_test.py
"""
import json
import os
import sys
import time

from gi.repository import Gio, GLib

UUID = "workspace-switcher-desklet@mgldvd"
CONFIG_DIR = os.path.expanduser(f"~/.config/cinnamon/spices/{UUID}")

bus = Gio.bus_get_sync(Gio.BusType.SESSION)
passed, failed = 0, 0


def call(method, signature, *args):
    return bus.call_sync("org.Cinnamon", "/org/Cinnamon", "org.Cinnamon", method,
                         GLib.Variant(signature, args), None, Gio.DBusCallFlags.NONE, 10000, None).unpack()


def js(body):
    """Run JS inside Cinnamon; D is the desklet, M its module, wm the workspace manager."""
    code = (f"(function(){{ const wm = global.workspace_manager;"
            f" const M = imports.misc.fileUtils.getModuleByIndex("
            f"   imports.ui.extension.getExtension('{UUID}').moduleIndex);"
            f" const D = Main.deskletContainer.actor.get_children().map(a => a._delegate)"
            f"   .find(d => d && d._uuid === '{UUID}'); {body} }})()")
    ok, result = call("Eval", "(s)", code)
    if not ok:
        raise RuntimeError(f"JS error: {result}\n  in: {body}")
    return json.loads(result) if result else None


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ok    {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


class Instance:
    def __init__(self):
        entries = [e for e in Gio.Settings.new("org.cinnamon").get_strv("enabled-desklets")
                   if e.startswith(UUID + ":")]
        if not entries:
            sys.exit(f"{UUID} is not on the desktop. Add it first (right-click desktop → Add Desklets).")
        _, self.id, self.x, self.y = entries[0].split(":")
        self.config = os.path.join(CONFIG_DIR, self.id + ".json")
        self.original = open(self.config).read()

    def set(self, key, value):
        data = json.load(open(self.config))
        data[key]["value"] = value
        json.dump(data, open(self.config, "w"), indent=4)
        call("updateSetting", "(ssss)", UUID, self.id, key, json.dumps(value))
        time.sleep(0.05)

    def restore(self):
        open(self.config, "w").write(self.original)
        # updateSetting re-reads the whole file and fires every changed key's callback
        call("updateSetting", "(ssss)", UUID, self.id, "position", "")
        js(f"if (D.position === 'manual') D.actor.set_position({self.x}, {self.y});")


def test_conversions():
    print("Label conversions")
    roman = js("return [4, 9, 14, 40, 90, 1994].map(n => M.toRoman(n));")
    check("toRoman", roman == ["IV", "IX", "XIV", "XL", "XC", "MCMXCIV"], roman)
    letters = js("return [1, 26, 27, 52, 53, 702, 703].map(n => M.toLetters(n));")
    check("toLetters", letters == ["A", "Z", "AA", "AZ", "BA", "ZZ", "AAA"], letters)


def test_layout(inst, n):
    print("Layout")
    inst.set("per-line", 0)
    inst.set("orientation", "horizontal")
    lines = js("return D._box.get_children().map(l => [l.vertical, l.get_n_children()]);")
    check("horizontal = one row", lines == [[False, n]], lines)
    inst.set("orientation", "vertical")
    lines = js("return D._box.get_children().map(l => [l.vertical, l.get_n_children()]);")
    check("vertical = one column", lines == [[True, n]], lines)
    if n >= 3:
        inst.set("per-line", 2)
        sizes = js("return D._box.get_children().map(l => l.get_n_children());")
        expected = [2] * (n // 2) + ([n % 2] if n % 2 else [])
        check("per-line 2 splits into lines of 2", sizes == expected, sizes)
        inst.set("per-line", 0)
    inst.set("orientation", "horizontal")


def test_size_and_style(inst):
    print("Size and style")
    inst.set("width", 120)
    inst.set("height", 70)
    inst.set("border-width", 3)
    inst.set("border-width-active", 6)
    inst.set("border-radius", 9)
    sizes = js("return D._box._rects.map(r => r.get_size().join('x'));")
    check("every rectangle is 120x70 (thicker active border included)",
          set(sizes) == {"120x70"}, sizes)
    inst.set("bg-color", "rgba(1,2,3,0.4)")
    inst.set("border-color-active", "rgb(9,8,7)")
    style = js("let a = wm.get_active_workspace_index();"
               "return [D._box._rects[a].get_style(), D._box._rects[(a + 1) % D._box._rects.length].get_style()];")
    check("active style uses active border color and width", "6px solid rgb(9,8,7)" in style[0], style[0])
    check("normal style uses normal background", "background-color: rgba(1,2,3,0.4)" in style[1], style[1])
    check("corner radius applied", "border-radius: 9px" in style[1], style[1])


def test_labels(inst, n):
    print("Labels")
    expected = {
        "none": [""] * n,
        "number": [str(i + 1) for i in range(n)],
        "roman": ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"][:n],
        "letter-lower": [chr(97 + i) for i in range(n)],
    }
    for mode, labels in expected.items():
        inst.set("label-mode", mode)
        got = js("return D._box._rects.map(r => r.child.text);")
        check(f"label mode '{mode}'", got == labels, got)
    inst.set("label-mode", "name")
    inst.set("custom-names", [{"workspace": 1, "name": "Web"}, {"workspace": 2, "name": ""}])
    got = js("return D._box._rects.map(r => r.child.text);")
    fallback = js("return Main.getWorkspaceName(1);")
    check("custom name used, empty name falls back", got[0] == "Web" and got[1] == fallback, got[:2])


def test_positions(inst):
    print("Positions")
    inst.set("monitor", "primary")
    inst.set("margin", 20)
    for position in ["top-left", "top-center", "bottom-right", "center-center"]:
        inst.set("position", position)
        x, y, w, h, ax, ay, aw, ah = js(
            "let a = wm.get_active_workspace().get_work_area_for_monitor(Main.layoutManager.primaryIndex);"
            "let [w, h] = D.actor.get_size(); let [x, y] = D.actor.get_position();"
            "return [x, y, w, h, a.x, a.y, a.width, a.height];")
        v, hz = position.split("-")
        ex = {"left": ax + 20, "right": ax + aw - w - 20, "center": ax + (aw - w) / 2}[hz]
        ey = {"top": ay + 20, "bottom": ay + ah - h - 20, "center": ay + (ah - h) / 2}[v]
        check(f"position '{position}'", abs(x - round(ex)) <= 1 and abs(y - round(ey)) <= 1,
              f"got {x},{y} expected {round(ex)},{round(ey)}")


def test_monitors(inst):
    print("Monitors")
    monitors = js("return Main.layoutManager.monitors.length;")
    inst.set("position", "top-center")
    inst.set("monitor", "all")
    clones = js("return D._clones.map(c => [c._monitor, c._rects.length]);")
    check(f"all monitors = {monitors - 1} copies", len(clones) == monitors - 1, clones)
    inst.set("monitor", "primary")
    check("primary = no copies", js("return D._clones.length;") == 0)

    options = js("return Object.values(D.settings.getOptions('monitor'));")
    expected = ["primary", "all"] + [str(i) for i in range(monitors)]
    check(f"monitor list offers the {monitors} connected monitor(s)", options == expected, options)
    inst.set("monitor", "7")
    home, primary = js("return [D._home, Main.layoutManager.primaryIndex];")
    check("missing monitor falls back to primary", home == primary, f"home {home}, primary {primary}")
    inst.set("monitor", "primary")


def test_reload(inst):
    print("Reload")
    monitors = js("return Main.layoutManager.monitors.length;")
    inst.set("monitor", "all")
    call("ReloadXlet", "(ss)", UUID, "DESKLET")
    time.sleep(1.5)  # the old instance fades out before it is removed
    registered = js(f"return Main.settingsManager.uuids['{UUID}']['{inst.id}'] === D.settings;")
    check("new instance keeps its settings registered", registered)
    clones = js("return Main.deskletContainer.actor.get_parent().get_children()"
                ".filter(a => a._monitor !== undefined && a._rects).length;")
    check(f"no leftover copies ({monitors - 1} expected)", clones == monitors - 1, clones)
    inst.set("width", 90)
    check("settings still apply after reload", js("return D._box._rects[0].get_width();") == 90)
    inst.set("monitor", "primary")


def test_scroll(inst, n):
    print("Mouse wheel")
    scroll = ("return D._onScroll({get_scroll_direction: () => imports.gi.Clutter.ScrollDirection.%s,"
              " is_pointer_emulated: () => false})"
              " + ':' + wm.get_active_workspace_index();")
    js(f"wm.get_workspace_by_index({n - 1}).activate(global.get_current_time());")
    inst.set("scroll-switch", True)
    inst.set("scroll-wrap", False)
    check("no wrap: stays on last", js(scroll % "DOWN") == f"true:{n - 1}")
    inst.set("scroll-wrap", True)
    check("wrap: last -> first", js(scroll % "DOWN") == "true:0")
    check("wrap: first -> last", js(scroll % "UP") == f"true:{n - 1}")
    inst.set("scroll-switch", False)
    check("disabled: event not handled", js(scroll % "UP") == f"false:{n - 1}")


def test_touchpad(inst, n):
    print("Touchpad")
    # (time in ms, vertical delta) -> workspace expected afterwards
    smooth = ("return D._onScroll({get_scroll_direction: () => imports.gi.Clutter.ScrollDirection.SMOOTH,"
              " get_scroll_delta: () => [0, %s], get_time: () => %d}) + ':' + wm.get_active_workspace_index();")
    emulated = ("return D._onScroll({get_scroll_direction: () => imports.gi.Clutter.ScrollDirection.DOWN,"
                " is_pointer_emulated: () => true}) + ':' + wm.get_active_workspace_index();")
    js("wm.get_workspace_by_index(0).activate(global.get_current_time());"
       "D._scrollTime = 0; D._scrollBlockedUntil = 0; D._scrollDelta = 0;")
    inst.set("scroll-switch", True)
    inst.set("scroll-wrap", False)
    t = 10_000_000
    check("small delta: no switch yet", js(smooth % (0.5, t)) == "true:0")
    check("deltas add up to a switch", js(smooth % (0.5, t + 10)) == "true:1")
    check("rest of the swipe ignored", js(smooth % (3, t + 20)) == "true:1")
    check("emulated wheel step ignored", js(emulated) == "true:1")
    check("new swipe switches back", js(smooth % (-1, t + 500)) == "true:0")


def main():
    inst = Instance()
    n = js("return wm.get_n_workspaces();")
    start_ws = js("return wm.get_active_workspace_index();")
    print(f"Testing instance {inst.id} with {n} workspaces\n")
    try:
        test_conversions()
        test_layout(inst, n)
        test_size_and_style(inst)
        test_labels(inst, n)
        test_positions(inst)
        test_monitors(inst)
        if n >= 2:
            test_scroll(inst, n)
            test_touchpad(inst, n)
        test_reload(inst)
    finally:
        inst.restore()
        js(f"wm.get_workspace_by_index({start_ws}).activate(global.get_current_time());")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
