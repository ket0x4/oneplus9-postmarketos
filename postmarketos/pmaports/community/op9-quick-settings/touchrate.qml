import QtQuick
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.plasma.private.mobileshell.quicksettingsplugin as QS

// Touchscreen report rate: 360 Hz (stock's game mode) or 120 Hz.
//
// The kernel exposes report_rate for both touch controllers this port drives
// (synaptics-tcm-i2c on the 9 Pro, s6sy761 on the 9). It lives in sysfs, which
// does not survive a reboot, so the choice is also written to
// ~/.config/op9-tuning.ini and re-applied at login by op9-tuning-restore.service.
QS.QuickSetting {
    id: root
    text: "Touch 360 Hz"
    // probed is false until the first poll: showing "Unavailable" or disabling the
    // tile before then would be wrong on a phone that has the knob.
    status: !probed ? "…" : (knob === "" ? "Unavailable"
                             : (rate === "360" ? "360 Hz" : "120 Hz"))
    icon: "input-touchpad-symbolic"
    enabled: knob !== ""

    property bool probed: false
    property string knob: ""
    property string rate: ""

    // A glob, not `find`: these sysfs directories are full of symlink loops (the
    // regulator/supplier links), and find either gives up or walks forever.
    readonly property string findCmd: "ls /sys/bus/i2c/drivers/synaptics-tcm-i2c" +
        "/*/report_rate /sys/bus/i2c/drivers/s6sy761/*/report_rate 2>/dev/null | head -n1"

    Plasma5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []

        onNewData: function(source, data) {
            var out = (data["stdout"] || "").trim();

            if (source === root.findCmd) {
                root.probed = true;
                root.knob = out;
                if (out !== "")
                    exec.connectSource("cat " + out);
            } else if (out === "120" || out === "240" || out === "360") {
                // only the knob's own contents are "120"/"240"/"360"
                root.rate = out;
            }
            disconnectSource(source);
        }
    }

    function refresh() {
        exec.connectSource(root.findCmd);
    }

    function toggle() {
        if (root.knob === "")
            return;
        var next = root.rate === "360" ? "120" : "360";
        // sysfs wants one write(); `echo` is that. The knob is group-writable by
        // `video` (see rootfs/etc/udev/rules.d/74-op9-tuning.rules).
        exec.connectSource("sh -c 'echo " + next + " > " + root.knob + "'");
        exec.connectSource("kwriteconfig6 --file \"$HOME/.config/op9-tuning.ini\" " +
                           "--group quick-settings --key touch-360hz " +
                           (next === "360" ? "true" : "false"));
        root.rate = next;
    }

    Timer {
        id: pollTimer
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Timer {
        id: settleTimer
        interval: 700
        running: false
        repeat: false
        onTriggered: root.refresh()
    }

    // Pick up a change made from the CLI or by tuned, and let the write settle.
    onRateChanged: settleTimer.restart()
}
