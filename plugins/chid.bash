# CHID Bash Plugin Integration
export CHID_SESSION="${CHID_SESSION:-$$_${SECONDS:-0}}"

_chid_in_prompt=0

_chid_preexec() {
    [ "${_chid_in_prompt:-0}" -eq 1 ] && return
    [ -n "$_CHID_ACTIVE" ] && return
    local cmd="$1"
    # Ignore empty commands
    [ -z "${cmd// }" ] && return
    # Ignore internal commands, chid, or alias invocations
    case "$cmd" in
        chid*|_chid*|PROMPT_COMMAND*|${CHID_ALIAS:+"$CHID_ALIAS"*} ) return ;;
    esac
    _CHID_ACTIVE=1
    command chid record-start "$PWD" "$CHID_SESSION" "$cmd" ${CHID_ALIAS:+--alias "$CHID_ALIAS"} &>/dev/null &
}

_chid_prompt_command() {
    local last_status=$?
    _chid_in_prompt=1
    if [ -n "$_CHID_ACTIVE" ]; then
        unset _CHID_ACTIVE
        command chid record-finish "$CHID_SESSION" "$last_status" &>/dev/null &
    fi
    _chid_in_prompt=0
    return $last_status
}

# Install preexec trap for Bash if not already present
if ! declare -F preexec >/dev/null 2>&1; then
    trap '_chid_preexec "$BASH_COMMAND"' DEBUG
fi

PROMPT_COMMAND="_chid_prompt_command${PROMPT_COMMAND:+; $PROMPT_COMMAND}"

_chid_replace_bash() {
    local line="${READLINE_LINE}"
    local replaced
    replaced=$(command chid replace "$CHID_SESSION" "$line" ${CHID_ALIAS:+--alias "$CHID_ALIAS"} 2>/dev/null)
    if [ -n "$replaced" ] && [ "$replaced" != "$line" ]; then
        READLINE_LINE="$replaced"
        READLINE_POINT=${#READLINE_LINE}
    fi
}

bind -x '"\C-@": _chid_replace_bash' 2>/dev/null || true
bind -x '"\C- ": _chid_replace_bash' 2>/dev/null || true
