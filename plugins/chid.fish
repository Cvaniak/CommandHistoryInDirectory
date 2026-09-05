# CHID Fish Plugin Integration
set -gx CHID_SESSION (string default (random 100000 999999) $CHID_SESSION)
set -g _chid_active 0

function _chid_preexec --on-event fish_preexec
    set -l cmd (string trim $argv[1])
    test -z "$cmd"; and return
    string match -q "chid*" "$cmd"; and return
    if test -n "$CHID_ALIAS"
        string match -q "$CHID_ALIAS*" "$cmd"; and return
    end

    set -g _chid_active 1
    chid record-start $PWD $CHID_SESSION $argv[1] 2>/dev/null &
    disown
end

function _chid_postexec --on-event fish_postexec
    set -l last_status $status
    if test "$_chid_active" = 1
        set -g _chid_active 0
        chid record-finish $CHID_SESSION $last_status 2>/dev/null &
        disown
    end
end

function _chid_replace_fish
    set -l cmd (commandline)
    set -l replaced (chid replace $CHID_SESSION "$cmd" 2>/dev/null)
    if test -n "$replaced" -a "$replaced" != "$cmd"
        commandline -r "$replaced"
    end
end

bind \c@ _chid_replace_fish 2>/dev/null || true
bind \c' ' _chid_replace_fish 2>/dev/null || true
