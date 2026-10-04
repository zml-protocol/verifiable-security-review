# Code context — vuln revision


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
 677  	if isHyperlink {
 678  		builder.WriteRune(s)
 679  		return
 680  	}
 681  
 682  	// UNSOLVABLE: When "Interactive" is true, the prompt length calculation in Bash/Zsh can be wrong, since the final string expansion is done by shells.
 683  	length += runewidth.RuneWidth(s)
 684  	// length += utf8.RuneCountInString(string(s))
 685  
 686  	if !Interactive && !Plain {
 687  		escaped, shouldEscape := formats.EscapeSequences[s]
 688  		if shouldEscape {
 689  			builder.WriteString(escaped)
 690  			return
 691  		}
 692  	}
 693  
 694  	builder.WriteRune(s)
 695  }
 696  
 697  // writeVisibleRune stamps the active gradient color(s) for the current cell
 698  // before writing s, then advances cellIndex by s's rune width. It is only
 699  // called from writeBodyGradient, so isInvisible/isHyperlink runes are
 700  // excluded from stamping and the index exactly like write() excludes them
 701  // from length.
 702  func writeVisibleRune(s rune) {
 703  	visible := !isInvisible && !isHyperlink
 704  
 705  	if visible {
 706  		stampGradient()
 707  	}
```
