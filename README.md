<p align="center">
  <h2 align="center"> 🔍 Command History In Repository (CHID)</h2>
</p>

<p align="center">
 Creates hisotry for current directory
</p>

> :warning: Project is in testing phase so history format may
change in next version

# :flashlight: Demo

![Demo](https://raw.githubusercontent.com/Cvaniak/CommandHistoryInDirectory/master/docs/DemoCHIDShort.gif)  

# :bulb: Motivation

This code stores command history for current directory
and allows you to display it.  
This idea is result of problem that
I always forget commands used at the beginning of the project.  

# :gear: Installation

Add to your `.zshrc` this line, where <path/to/chid_directory>
should be path to this repo.

* source <path/to/chid_directory>/chid_plugin.zsh

If you want use alias do it with `CHID_ALIAS` like this:

```bash
CHID_ALIAS=your_custom_alias
CHID_SHORTCUT='^ ' # Default for Ctrl+SPACE
# for example ~/chid_directory/chid_plugin.zsh
source <path/to/chid_directory>/chid_plugin.zsh
```

you can also setup custom shortcut for buffer replacement with `CHID_SHORTCUT`.

# :hammer_and_wrench: Usage

* To list commands used in current directory run `chid`.
* To list commands by time of first occurance use `-sf` or last occurance `-sl`.
* By default `chid` displays first 20 lines of output.
You can change it with `-l <num>` or `--limit <num>`.

> Not tested well yet:
>
> * You can get command to buffer by `chid number` e.g. `chid 1`
and then running your shortcut (default to Ctrl+SPACE)

# :memo: TODO

* ⭕ Reverse List
* ✔️  Display by date
* ✔️  Limit output
* ⭕ Better way to search commands in directory
* ⭕ Support multiline commands (now they might not work well...)
* ⭕ Sort by command (without arguments and flags)

# :eyes: Similar projects

While making this project I found very similar but with a little diffrent goal.
Maybe you will like it more:

* [zsh-directory-history](https://github.com/tymm/zsh-directory-history)
