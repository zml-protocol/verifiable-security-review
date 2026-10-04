// Go syntax-node resolver for the frozen RD anchor matcher.
//
// Reads Go source on stdin and a target span from argv; emits the canonical syntax-node identity of
// the tightest AST node containing that span. Identity is position-independent (so the same node
// under different formatting matches) but distinguishes two identical-text nodes at different
// positions via the structural path (the root->node child-ordinal path).
//
// argv: start_line start_col end_line end_col   (line 1-based, col 0-based; end exclusive-ish,
// compared with <= / >= so an exact node span matches).
//
// Comments are excluded (parse mode 0) so reformatting/comments never shift the structural path.
// Output (stdout, JSON): {"node_type","structural_path":[int...],"content_digest"}.
// Any failure prints an error to stderr and exits non-zero (the Python side turns that into a
// fail-loud SystemExit).
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/printer"
	"go/token"
	"io"
	"os"
	"strconv"
)

type pos struct{ line, col int } // line 1-based, col 0-based

func le(a, b pos) bool { return a.line < b.line || (a.line == b.line && a.col <= b.col) }

func main() {
	if len(os.Args) != 5 {
		fmt.Fprintln(os.Stderr, "usage: node_id start_line start_col end_line end_col < source")
		os.Exit(2)
	}
	nums := make([]int, 4)
	for i := 0; i < 4; i++ {
		v, err := strconv.Atoi(os.Args[i+1])
		if err != nil {
			fmt.Fprintln(os.Stderr, "bad span arg:", err)
			os.Exit(2)
		}
		nums[i] = v
	}
	tStart := pos{nums[0], nums[1]}
	tEnd := pos{nums[2], nums[3]}

	src, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Fprintln(os.Stderr, "read stdin:", err)
		os.Exit(1)
	}
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, "src.go", src, 0) // mode 0: no comments
	if err != nil {
		fmt.Fprintln(os.Stderr, "parse:", err)
		os.Exit(1)
	}

	// Build parent -> ordered direct children (source order, as ast.Inspect visits them) and the
	// reverse parent map, using the nil-sentinel ast.Inspect emits after a node's children.
	children := map[ast.Node][]ast.Node{}
	parentOf := map[ast.Node]ast.Node{}
	var stack []ast.Node
	ast.Inspect(f, func(n ast.Node) bool {
		if n == nil {
			stack = stack[:len(stack)-1]
			return true
		}
		if len(stack) > 0 {
			p := stack[len(stack)-1]
			children[p] = append(children[p], n)
			parentOf[n] = p
		}
		stack = append(stack, n)
		return true
	})

	span := func(n ast.Node) (pos, pos) {
		s := fset.Position(n.Pos())
		e := fset.Position(n.End())
		return pos{s.Line, s.Column - 1}, pos{e.Line, e.Column - 1}
	}

	// Tightest node whose span contains the target span; tie-break by deepest (smallest span).
	var best ast.Node
	var bestStart, bestEnd pos
	ast.Inspect(f, func(n ast.Node) bool {
		if n == nil {
			return true
		}
		ns, ne := span(n)
		if le(ns, tStart) && le(tEnd, ne) {
			if best == nil || (le(bestStart, ns) && le(ne, bestEnd)) {
				best, bestStart, bestEnd = n, ns, ne
			}
		}
		return true
	})
	if best == nil || best == ast.Node(f) {
		fmt.Fprintln(os.Stderr, "no enclosing node for the target span")
		os.Exit(1)
	}

	// Structural path: ordinal of each ancestor-child step from the File root down to best.
	var rev []int
	for n := best; ; {
		p, ok := parentOf[n]
		if !ok {
			break
		}
		idx := -1
		for i, c := range children[p] {
			if c == n {
				idx = i
				break
			}
		}
		rev = append(rev, idx)
		n = p
	}
	path := make([]int, len(rev))
	for i := range rev {
		path[i] = rev[len(rev)-1-i]
	}

	// Content digest: gofmt-normalised print of the node (formatting-invariant), hashed.
	var buf bytes.Buffer
	digest := ""
	if err := printer.Fprint(&buf, fset, best); err == nil {
		sum := sha256.Sum256(buf.Bytes())
		digest = fmt.Sprintf("%x", sum[:])
	}

	out, _ := json.Marshal(map[string]any{
		"node_type":       fmt.Sprintf("%T", best),
		"structural_path": path,
		"content_digest":  digest,
	})
	os.Stdout.Write(out)
}
