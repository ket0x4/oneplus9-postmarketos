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
    echo "$max_hz" > "$dir/max_freq" 2>/dev/null || true
    echo "$min_hz" > "$dir/min_freq" 2>/dev/null || true
    [ -n "$poll_ms" ] && [ -w "$dir/polling_interval" ] && echo "$poll_ms" > "$dir/polling_interval" 2>/dev/null || true
}

start() {
    # A55: 998 MHz - 1.80 GHz, A78: 1.21 GHz - 2.42 GHz, X1: 1.31 GHz - 2.84 GHz
    set_cpufreq 0 998400 1804800 500
    set_cpufreq 4 1209600 2419200 500
    set_cpufreq 7 1305600 2841600 500

    # Adreno 660 GPU: 443 MHz - 840 MHz (20ms poll); UFS: 300 MHz (50ms poll)
    set_devfreq 3d00000.gpu 443000000 840000000 20
    set_devfreq 1d84000.ufshc 300000000 300000000 50

    # Touchscreen report rate: 360 Hz in performance mode
    for f in /sys/bus/i2c/drivers/s6sy761/*/report_rate /sys/bus/i2c/drivers/synaptics-tcm-i2c/*/report_rate; do
        [ -w "$f" ] && echo 360 > "$f" 2>/dev/null || true
    done

    # Discover the interface: the name differs between distributions.
    for w in /sys/class/net/*/wireless; do
        [ -e "$w" ] && iw dev "${w%/wireless}" set power_save off 2>/dev/null || true
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
