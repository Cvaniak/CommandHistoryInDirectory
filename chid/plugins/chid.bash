# CHID Bash Plugin Integration
export CHID_SESSION="${CHID_SESSION:-$$_${SECONDS:-0}}"

_chid_preexec() {
    local cmd="$1"
    # Ignore empty commands
    [ -z "${cmd// }" ] && return
    # Ignore chid or alias commands
    case "$cmd" in
        chid*|${CHID_ALIAS:+"$CHID_ALIAS"*} ) return ;;
    esac
    _CHID_ACTIVE=1
    chid record-start "$PWD" "$CHID_SESSION" "$cmd" ${CHID_ALIAS:+--alias "$CHID_ALIAS"} 2>/dev/null &
}

_chid_prompt_command() {
    local last_status=$?
    if [ -n "$_CHID_ACTIVE" ]; then
        unset _CHID_ACTIVE
        chid record-finish "$CHID_SESSION" "$last_status" 2>/dev/null &
    fi
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
    replaced=$(chid replace "$CHID_SESSION" "$line" ${CHID_ALIAS:+--alias "$CHID_ALIAS"} 2>/dev/null)
    if [ -n "$replaced" ] && [ "$replaced" != "$line" ]; then
        READLINE_LINE="$replaced"
        READLINE_POINT=${#READLINE_LINE}
    fi
}

bind -x '"\C-@": _chid_replace_bash' 2>/dev/null || true
bind -x '"\C- ": _chid_replace_bash' 2>/dev/null || true
