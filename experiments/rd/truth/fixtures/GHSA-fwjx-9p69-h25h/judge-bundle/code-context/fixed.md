# Code context — fixed revision


## src/terminal/writer.go (lines 652-707)

```go
 652  func writeColorise(c color.Ansi) {
 653  	if c.IsEmpty() || c.IsGradient() {
 654  		return
 655  	}
 656  
 657  	writeEscapedAnsiParts(colorisePrefix, c, coloriseSuffix)
 658  }
 659  
 660  // writeTransparentStart writes the equivalent of fmt.Sprintf(transparentStart, c)
 661  // wrapped in the shell escape sequence, without allocating an intermediate string.
 662  // The empty/gradient guard mirrors writeColorise: \x1b[;49m\x1b[7m would run
 663  // reverse video against default colors instead of the intended payload.
 664  func writeTransparentStart(c color.Ansi) {
 665  	if c.IsEmpty() || c.IsGradient() {
 666  		return
 667  	}
 668  
 669  	writeEscapedAnsiParts(transparentStartPrefix, c, transparentStartSuffix)
 670  }
 671  
 672  func write(s rune) {
 673  	if isInvisible {
 674  		return
 675  	}
 676  
 677  	// segment content (directory names, git metadata, environment variables,
 678  	// command output) is potentially attacker-controlled and never passes through
 679  	// this function when it's Oh My Posh's own styling; drop C0/C1 control runes
 680  	// (ESC, BEL, CSI, OSC, ...) so they can't be interpreted as escape sequences
 681  	// by the terminal, including inside a hyperlink target.
 682  	if isControlRune(s) {
 683  		return
 684  	}
 685  
 686  	if isHyperlink {
 687  		builder.WriteRune(s)
 688  		return
 689  	}
 690  
 691  	// UNSOLVABLE: When "Interactive" is true, the prompt length calculation in Bash/Zsh can be wrong, since the final string expansion is done by shells.
 692  	length += runewidth.RuneWidth(s)
 693  	// length += utf8.RuneCountInString(string(s))
 694  
 695  	if !Interactive && !Plain {
 696  		escaped, shouldEscape := formats.EscapeSequences[s]
 697  		if shouldEscape {
 698  			builder.WriteString(escaped)
 699  			return
 700  		}
 701  	}
 702  
 703  	builder.WriteRune(s)
 704  }
 705  
 706  // isControlRune reports whether s is a C0 (0x00-0x1F), DEL (0x7F), or C1
 707  // (0x80-0x9F) control character. These are the bytes a terminal can interpret
```
