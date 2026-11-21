#!/bin/sh

. /usr/lib/tuned/functions

set_cpufreq() {
    policy="$1"
    min_khz="$2"
    max_khz="$3"
    rate_us="$4"
    dir="/sys/devices/system/cpu/cpufreq/policy${policy}"
    [ -d "$dir" ] || return 0
    echo schedutil > "$dir/scaling_governor" 2>/dev/null || true
    echo "$min_khz" > "$dir/scaling_min_freq" 2>/dev/null || true
    echo "$max_khz" > "$dir/scaling_max_freq" 2>/dev/null || true
    echo "$min_khz" > "$dir/scaling_min_freq" 2>/dev/null || true
    [ -w "$dir/schedutil/rate_limit_us" ] && echo "$rate_us" > "$dir/schedutil/rate_limit_us" 2>/dev/null || true
}

set_devfreq() {
    dev="$1"
    min_hz="$2"
    max_hz="$3"
    poll_ms="$4"
    dir="/sys/class/devfreq/${dev}"
    [ -d "$dir" ] || return 0
    echo simple_ondemand > "$dir/governor" 2>/dev/null || true
    echo "$min_hz" > "$dir/min_freq" 2>/dev/null || true
    echo "$max_hz" > "$dir/max_freq" 2>/dev/null || true
    echo "$min_hz" > "$dir/min_freq" 2>/dev/null || true
    [ -n "$poll_ms" ] && [ -w "$dir/polling_interval" ] && echo "$poll_ms" > "$dir/polling_interval" 2>/dev/null || true
}

start() {
    # A55: 300 MHz - 1.50 GHz, A78: 710 MHz - 1.67 GHz, X1: 845 MHz - 1.67 GHz
    set_cpufreq 0 300000 1497600 4000
    set_cpufreq 4 710400 1670400 4000
    set_cpufreq 7 844800 1670400 4000

    # Adreno 660 GPU: 315 MHz - 491 MHz (100ms poll); UFS: 75 MHz - 300 MHz (100ms poll)
    set_devfreq 3d00000.gpu 315000000 491000000 100
    set_devfreq 1d84000.ufshc 75000000 300000000 100

    # Touchscreen report rate: 120 Hz in power-save
    for f in /sys/bus/i2c/drivers/s6sy761/*/report_rate /sys/bus/i2c/drivers/synaptics-tcm-i2c/*/report_rate; do
        [ -w "$f" ] && echo 120 > "$f" 2>/dev/null || true
    done

    # Discover the interface: the name differs (wlan0 on Alpine/iwd, wlp1s0 on
    # Arch), and hardcoding both misses anything else.
    for w in /sys/class/net/*/wireless; do
        [ -e "$w" ] && iw dev "${w%/wireless}" set power_save on 2>/dev/null || true
    done
    for p in /sys/bus/pci/devices/*/power/control; do
        [ -w "$p" ] && echo auto > "$p" 2>/dev/null || true
    done
    systemctl try-restart touchboost.service 2>/dev/null || true
    return 0
}

stop() {
    return 0
}

# tuned calls this with the profile name; it must word-split
# shellcheck disable=SC2068
process $@
