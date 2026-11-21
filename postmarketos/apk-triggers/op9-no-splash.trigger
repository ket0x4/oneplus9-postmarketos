# apk trigger: regenerate the launcher overrides that skip Phosh's loading splash
# after anything installs a desktop file. Replaces rootfs/etc/pacman.d/hooks/.
# Called as `op9-no-splash --hook`, which reruns it as the phone's own user.
type = path
path = usr/share/applications/*.desktop
