package main

import (
	"archive/zip"
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func fixture(t *testing.T) ([]byte, release) {
	t.Helper()
	var out bytes.Buffer
	z := zip.NewWriter(&out)
	for n, data := range map[string]string{"main.blyx": "fn main() {}", "expected.txt": "", "vendor/sample/Blyx.toml": "[package]", "vendor/sample/sample.blyx": "pub fn one() -> i64 { 1 }"} {
		f, err := z.Create(n)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := f.Write([]byte(data)); err != nil {
			t.Fatal(err)
		}
	}
	if err := z.Close(); err != nil {
		t.Fatal(err)
	}
	blob := out.Bytes()
	return blob, release{"1.0.0", fmt.Sprintf("%x", sha256.Sum256(blob)), int64(len(blob))}
}

func TestInstallAndRestore(t *testing.T) {
	t.Chdir(t.TempDir())
	if err := os.Mkdir("src", 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile("src/main.blyx", nil, 0644); err != nil {
		t.Fatal(err)
	}
	blob, rel := fixture(t)
	record := map[string]any{"slug": "sample", "title": "Sample", "kind": "library", "module": "sample", "latest": rel.Version, "versions": []release{rel}}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/v1/packages/sample.json":
			json.NewEncoder(w).Encode(record)
		case "/files/sample/1.0.0.zip":
			w.Write(blob)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	t.Setenv("BLYX_NEST_URL", server.URL)
	for _, args := range [][]string{{"add", "sample@1.0.0"}, {"add", "sample"}, {"install"}, {"demo", "sample"}} {
		if err := run(args); err != nil {
			t.Fatal(err)
		}
	}
	module := filepath.Join("src", "vendor", "sample", "sample.blyx")
	if _, err := os.Stat(module); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat("sample-demo/main.blyx"); err != nil {
		t.Fatal(err)
	}
	if err := run([]string{"demo", "sample"}); err == nil {
		t.Fatal("replaced existing demo")
	}
	if err := os.RemoveAll("src/vendor"); err != nil {
		t.Fatal(err)
	}
	if err := run([]string{"install"}); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(module, []byte("my changes"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := run([]string{"add", "sample"}); err == nil {
		t.Fatal("accepted changed module")
	}
	content, _ := os.ReadFile(module)
	if string(content) != "my changes" {
		t.Fatal("overwrote local changes")
	}
	blob[0] ^= 1
	if err := run([]string{"install"}); err == nil {
		t.Fatal("accepted corrupt download")
	}
}

func TestUnsafeArchivePath(t *testing.T) {
	var out bytes.Buffer
	z := zip.NewWriter(&out)
	f, _ := z.Create("vendor/x/../../escape")
	f.Write([]byte("unsafe"))
	z.Close()
	archive, err := zip.NewReader(bytes.NewReader(out.Bytes()), int64(out.Len()))
	if err != nil {
		t.Fatal(err)
	}
	if err := extract(archive, "x", "x", t.TempDir()); err == nil {
		t.Fatal("accepted unsafe archive path")
	}
}
