import QtQuick
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.plasma.private.mobileshell.quicksettingsplugin as QS

QS.QuickSetting {
    id: root
    text: "RDP Desktop"
    status: active ? "On (:3389)" : "Off"
    icon: "preferences-desktop-display-randr"
    enabled: active

    property bool active: false

    Plasma5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: function(source, data) {
            if (source === "systemctl --user is-active op9-rdp-desktop.service") {
                var out = (data["stdout"] || "").trim();
                root.active = (out === "active");
            } else {
                refreshTimer.restart();
            }
            disconnectSource(source);
        }
    }

    function refresh() {
        exec.connectSource("systemctl --user is-active op9-rdp-desktop.service");
    }

    Timer {
        id: pollTimer
        interval: 4000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Timer {
        id: refreshTimer
        interval: 800
        running: false
        repeat: false
        onTriggered: root.refresh()
    }

    function toggle() {
        if (root.active) {
            root.active = false;
            exec.connectSource("systemctl --user stop op9-rdp-desktop.service");
        } else {
            root.active = true;
            exec.connectSource("systemctl --user start op9-rdp-desktop.service");
        }
    }
}
