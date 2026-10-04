package fbhttp

// Ground-truth probe for fixtures/filebrowser-archive-backslash. The identical
// file is copied into http/ at both the base and the head commit; nothing
// else in either tree is modified.
//
// It follows rawDirHandler's own steps below the HTTP layer: select the
// archiver with parseQueryAlgorithm, collect entries with getFiles, write a
// real archive with the pinned archiver, then read the entry names back from
// the archive bytes. Only extraction is modelled (see escapes).

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http/httptest"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strings"
	"testing"

	"github.com/spf13/afero"

	"github.com/filebrowser/filebrowser/v2/fileutils"
	"github.com/filebrowser/filebrowser/v2/settings"
	"github.com/filebrowser/filebrowser/v2/users"
)

// escapes reports whether an extractor that splits entry names on the given
// separators and joins them naively under dest would write outside dest.
func escapes(name, seps string) bool {
	parts := strings.FieldsFunc(name, func(r rune) bool { return strings.ContainsRune(seps, r) })
	joined := path.Clean(path.Join(append([]string{"/dest"}, parts...)...))
	return joined != "/dest" && !strings.HasPrefix(joined, "/dest/")
}

func readBack(t *testing.T, algo string, data []byte) []string {
	var names []string
	switch algo {
	case "zip":
		zr, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
		if err != nil {
			t.Fatal(err)
		}
		for _, f := range zr.File {
			names = append(names, f.Name)
		}
	case "tar":
		tr := tar.NewReader(bytes.NewReader(data))
		for {
			hdr, err := tr.Next()
			if err == io.EOF {
				break
			}
			if err != nil {
				t.Fatal(err)
			}
			names = append(names, hdr.Name)
		}
	}
	sort.Strings(names)
	return names
}

func TestTruthProbe(t *testing.T) {
	root := t.TempDir()
	stored := []string{`..\..\evil.sh`, `a\b.txt`, "plain.txt"}
	if err := os.MkdirAll(filepath.Join(root, "dir"), 0o755); err != nil {
		t.Fatal(err)
	}
	for _, name := range stored {
		if err := os.WriteFile(filepath.Join(root, "dir", name), []byte("x"), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	d := &data{
		settings: &settings.Settings{},
		user:     &users.User{Fs: afero.NewBasePathFs(afero.NewOsFs(), root)},
	}
	// Same selection logic as rawDirHandler when the user downloads /dir.
	selected := []string{"/dir"}
	common := fileutils.CommonPrefix(filepath.Separator, selected...)

	report := map[string]any{"common_dir": common}
	for _, algo := range []string{"zip", "tar"} {
		_, archiver, err := parseQueryAlgorithm(httptest.NewRequest("GET", "/?algo="+algo, nil))
		if err != nil {
			t.Fatal(err)
		}
		files, err := getFiles(d, selected[0], common)
		if err != nil {
			t.Fatal(err)
		}
		var buf bytes.Buffer
		if err := archiver.Archive(context.Background(), &buf, files); err != nil {
			t.Fatal(err)
		}
		var entries []map[string]any
		for _, name := range readBack(t, algo, buf.Bytes()) {
			entries = append(entries, map[string]any{
				"entry":                     name,
				"contains_backslash":        strings.Contains(name, `\`),
				"escapes_posix_extractor":   escapes(name, "/"),
				"escapes_windows_extractor": escapes(name, `/\`),
			})
		}
		report[algo] = entries
	}
	out, _ := json.MarshalIndent(report, "", "  ")
	t.Logf("TRUTH %s", out)
}
