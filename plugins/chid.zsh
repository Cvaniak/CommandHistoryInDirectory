# Export unique session token
export CHID_SESSION="${CHID_SESSION:-$$_${EPOCHSECONDS:-$(date +%s)}}"

_chid_preexec() {
    # Ignore empty commands
    [[ -z "${1// }" ]] && return
    # Ignore chid or alias invocations
    [[ "$1" == chid* || ( -n "$CHID_ALIAS" && "$1" == "$CHID_ALIAS"* ) ]] && return
    _CHID_ACTIVE=1
    chid record-start "$PWD" "$CHID_SESSION" "$1" ${CHID_ALIAS:+--alias "$CHID_ALIAS"} 2>/dev/null
}

_chid_precmd() {
    local last_status=$?
    if [[ -n "$_CHID_ACTIVE" ]]; then
        unset _CHID_ACTIVE
        chid record-finish "$CHID_SESSION" "$last_status" 2>/dev/null
    fi
    return $last_status
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec _chid_preexec
add-zsh-hook precmd _chid_precmd

function _chid_replace() {
    local alias_pattern="${CHID_ALIAS:-chid}"
    if [[ "$BUFFER" =~ ^[[:space:]]*(chid|${alias_pattern})[[:space:]]+[0-9]+[[:space:]]*$ ]]; then
        local replaced
        replaced=$(chid replace "$CHID_SESSION" "$BUFFER" ${CHID_ALIAS:+--alias "$CHID_ALIAS"} 2>/dev/null)
        if [[ -n "$replaced" ]]; then
            BUFFER="$replaced"
            CURSOR=$#BUFFER
        fi
    fi
}
zle -N _chid_replace
bindkey "${CHID_SHORTCUT:-^ }" _chid_replace
[[ "${CHID_SHORTCUT:-^ }" == '^ ' ]] && bindkey '^@' _chid_replace
