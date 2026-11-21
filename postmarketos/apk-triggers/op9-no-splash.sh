#!/bin/sh
# apk trigger entry point for op9-no-splash.trigger. apk runs triggers from the
# package that owns them, so this lives next to the no-splash helper
# helper install rather than in a package of its own.
exec /usr/local/bin/op9-no-splash --hook
