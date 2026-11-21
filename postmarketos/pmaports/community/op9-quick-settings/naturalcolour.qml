import QtQuick
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.plasma.private.mobileshell.quicksettingsplugin as QS

// Natural colour: sRGB content mapped onto the panel's Display P3 gamut (stock's
// "Natural"), or the panel's native wide gamut (stock's default, "Vivid").
//
// This is the msm.natural_colour module parameter (patch 0148). It defaults to
// 0644, so the udev rule 74-op9-tuning.rules makes it group-writable by `video`
// and this runs as the session user. The parameter does not survive a reboot, so
// the choice is also written to ~/.config/op9-tuning.ini and re-applied at login
// by op9-tuning-restore.service.
QS.QuickSetting {
    id: root
    text: "Natural colour"
    status: available ? (natural ? "Natural (sRGB)" : "Vivid") : "Unavailable"
    icon: "applications-graphics-symbolic"
    enabled: available

    readonly property string param: "/sys/module/msm/parameters/natural_colour"
    property bool available: false
    property bool natural: false

    Plasma5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []

        onNewData: function(source, data) {
            var out = (data["stdout"] || "").trim();
            if (source === root.probeCmd) {
                // No parameter means patch 0148 is not in this kernel.
                root.available = (out === "yes");
                if (root.available && root.knob === "")
                    root.knob = root.param;
            } else if (source === root.readCmd) {
                root.natural = (out === "Y" || out === "1");
            }
            disconnectSource(source);
        }
    }

    // Filled in by the probe, so a missing parameter never reads as "Vivid".
    property string knob: ""

    readonly property string probeCmd: "test -e " + param + " && echo yes || echo no"
    readonly property string readCmd: "cat " + knob

    function refresh() {
        if (root.knob === "") {
            exec.connectSource(root.probeCmd);
            return;
        }
        exec.connectSource(root.readCmd);
    }

    function toggle() {
        var next = !root.natural;
        // One write, as the parameter expects; `echo` is that.
        exec.connectSource("sh -c 'echo " + (next ? "Y" : "N") + " > " + root.knob + "'");
        exec.connectSource("kwriteconfig6 --file \"$HOME/.config/op9-tuning.ini\" " +
                           "--group quick-settings --key natural-colour " +
                           (next ? "true" : "false"));
        root.natural = next;
    }

    Component.onCompleted: refresh()

    Timer {
        id: pollTimer
        interval: 5000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }
}
