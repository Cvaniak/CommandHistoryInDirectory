#!/bin/zsh

function _chid_append_new_command() {
    _DATE=$(date +"%s")
    python3 ~/this_history/chid_append.py "${PWD}" "${1}" "$_DATE" "$CHID_ALIAS"
}

preexec_functions=("${preexec_functions[@]}" "_chid_append_new_command")

function chid() {
    python3 ~/this_history/chid_command.py "$PWD" "$CHID_ALIAS" "$@"
}

function _chid_replace() {
    if [[ $BUFFER = chid* ]] || [[ $BUFFER = $CHID_ALIAS* ]]; then
        a=$(python3 ~/this_history/chid_replace.py "$PWD" "$BUFFER" "$CHID_ALIAS")
        BUFFER="$a"
    fi
}

if [[ ! -z $CHID_SHORTCUT ]]; then
    CHID_SHORTCUT='^ '
fi

if [[ ! -z $CHID_ALIAS ]]; then
    alias $CHID_ALIAS=chid
fi

zle -N _chid_replace
bindkey $CHID_SHORTCUT _chid_replace
# To be continued
# function _t_replace() {
#     if [[ $BUFFER = t* ]]; then
#         a=$(python3 ~/this_history/chid_replace.py "$PWD" "$BUFFER")
#     fi
# }
# complete -F _t_replace t
# zle accept-line
