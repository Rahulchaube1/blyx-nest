// Nest installs verified Blyx source into the import tree of a project.
package main

import (
	"archive/zip"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)

const version = "0.1.0"
const primary = "https://nest.blyx-lang.space"
const alternate = "https://www.blyx-lang.space/nest"
const maxArchive = 16 << 20
const maxExpanded = 48 << 20

var idPattern = regexp.MustCompile("^[a-z][a-z0-9_]{0,47}$")
var verPattern = regexp.MustCompile("^(0|[1-9][0-9]{0,8})\\.(0|[1-9][0-9]{0,8})\\.(0|[1-9][0-9]{0,8})$")
var hashPattern = regexp.MustCompile("^[0-9a-f]{64}$")
var partPattern = regexp.MustCompile("^[a-zA-Z0-9_-][a-zA-Z0-9_. -]{0,119}$")

type item struct{ Slug, Title, Kind, Description, Latest, Module string }
type release struct {
	Version, SHA256 string
	Size            int64
}
type metadata struct {
	item
	Versions []release
}
type pin struct {
	Slug    string `json:"slug"`
	Version string `json:"version"`
	SHA256  string `json:"sha256"`
}
type registry struct {
	bases []string
	http  *http.Client
}

func registryClient() (*registry, error) {
	bases := []string{primary, alternate}
	if override := os.Getenv("BLYX_NEST_URL"); override != "" {
		u, err := url.Parse(override)
		if err != nil {
			return nil, err
		}
		loopback := u.Hostname() == "localhost" || net.ParseIP(u.Hostname()).IsLoopback()
		if u.Host == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || !(u.Scheme == "https" || u.Scheme == "http" && loopback) {
			return nil, errors.New("BLYX_NEST_URL requires HTTPS or loopback HTTP")
		}
		bases = []string{strings.TrimSuffix(override, "/")}
	}
	return &registry{bases, &http.Client{Timeout: 25 * time.Second}}, nil
}

func (r *registry) get(name string, limit int64) ([]byte, error) {
	var last error
	for _, base := range r.bases {
		res, err := r.http.Get(base + "/" + name)
		if err != nil {
			last = err
			continue
		}
		if res.StatusCode != http.StatusOK {
			res.Body.Close()
			last = fmt.Errorf("%s returned %s", name, res.Status)
			continue
		}
		body, err := io.ReadAll(io.LimitReader(res.Body, limit+1))
		res.Body.Close()
		if err != nil {
			last = err
			continue
		}
		if int64(len(body)) > limit {
			return nil, fmt.Errorf("%s exceeds size limit", name)
		}
		return body, nil
	}
	return nil, last
}

func spec(argument string) (string, string, error) {
	slug, ver, pinned := strings.Cut(argument, "@")
	if !idPattern.MatchString(slug) || !filepath.IsLocal(slug) || (pinned && !verPattern.MatchString(ver)) {
		return "", "", errors.New("use a package ID or ID@X.Y.Z")
	}
	return slug, ver, nil
}

func (r *registry) resolve(slug, ver string) (metadata, release, error) {
	var m metadata
	body, err := r.get("api/v1/packages/"+slug+".json", 2<<20)
	if err != nil {
		return m, release{}, err
	}
	if err = json.Unmarshal(body, &m); err != nil {
		return m, release{}, err
	}
	if m.Slug != slug || !idPattern.MatchString(m.Module) || (m.Kind != "library" && m.Kind != "framework") {
		return m, release{}, errors.New("invalid registry metadata")
	}
	if ver == "" {
		ver = m.Latest
	}
	for _, v := range m.Versions {
		if v.Version == ver && verPattern.MatchString(ver) && hashPattern.MatchString(v.SHA256) && v.Size > 0 && v.Size <= maxArchive {
			return m, v, nil
		}
	}
	return m, release{}, fmt.Errorf("%s@%s is unavailable", slug, ver)
}

func (r *registry) unpack(slug, module string, v release, dest string) error {
	blob, err := r.get("files/"+slug+"/"+v.Version+".zip", maxArchive)
	if err != nil {
		return err
	}
	digest := sha256.Sum256(blob)
	if hex.EncodeToString(digest[:]) != v.SHA256 || int64(len(blob)) != v.Size {
		return errors.New("package size or SHA-256 mismatch")
	}
	archive, err := zip.NewReader(bytes.NewReader(blob), int64(len(blob)))
	if err != nil {
		return err
	}
	return extract(archive, slug, module, dest)
}

func extract(archive *zip.Reader, slug, module, dest string) error {
	if len(archive.File) > 1200 {
		return errors.New("too many files")
	}
	vendor := "vendor/" + slug + "/"
	seen := map[string]bool{}
	var total uint64
	for _, z := range archive.File {
		n := z.Name
		if !fs.ValidPath(n) || !filepath.IsLocal(filepath.FromSlash(n)) || !z.Mode().IsRegular() ||
			!(n == "main.blyx" || n == "expected.txt" || strings.HasPrefix(n, vendor)) {
			return errors.New("invalid file in package")
		}
		for _, part := range strings.Split(n, "/") {
			if !partPattern.MatchString(part) || strings.HasSuffix(part, ".") || strings.HasSuffix(part, " ") ||
				!filepath.IsLocal(part) {
				return fmt.Errorf("invalid path %q", n)
			}
		}
		key := strings.ToLower(n)
		if seen[key] || z.UncompressedSize64 > maxExpanded-total {
			return errors.New("duplicate path or oversized package")
		}
		total += z.UncompressedSize64
		seen[key] = true
		target := filepath.Join(dest, filepath.FromSlash(n))
		if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
			return err
		}
		if err := writeMember(z, target); err != nil {
			return err
		}
	}
	for _, n := range []string{"main.blyx", "expected.txt", vendor + "Blyx.toml", vendor + module + ".blyx"} {
		if !seen[strings.ToLower(n)] {
			return fmt.Errorf("missing %s", n)
		}
	}
	return nil
}

func writeMember(z *zip.File, target string) error {
	source, err := z.Open()
	if err != nil {
		return err
	}
	defer source.Close()
	file, err := os.OpenFile(target, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0644)
	if err != nil {
		return err
	}
	n, copyErr := io.Copy(file, io.LimitReader(source, int64(z.UncompressedSize64)+1))
	closeErr := file.Close()
	if copyErr != nil {
		return copyErr
	}
	if uint64(n) != z.UncompressedSize64 {
		return errors.New("incorrect expanded size")
	}
	return closeErr
}

func directory(name string) error {
	if err := os.Mkdir(name, 0755); err != nil && !os.IsExist(err) {
		return err
	}
	info, err := os.Lstat(name)
	if err != nil {
		return err
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("%s must be a directory", name)
	}
	return nil
}

// Pin files are independently committed. Concurrent adds cannot replace someone else's pin.
func savePin(dir string, p pin) error {
	if err := directory(dir); err != nil {
		return err
	}
	target := filepath.Join(dir, p.Slug+".json")
	file, err := os.CreateTemp(dir, ".pin-")
	if err != nil {
		return err
	}
	defer os.Remove(file.Name())
	err = json.NewEncoder(file).Encode(p)
	closeErr := file.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	if err = os.Link(file.Name(), target); err == nil {
		return nil
	}
	if !os.IsExist(err) {
		return err
	}
	original, err := readPin(target)
	if err != nil {
		return err
	}
	if original != p {
		return fmt.Errorf("a different %s release is locked in %s", p.Slug, target)
	}
	return nil
}

func readPin(name string) (pin, error) {
	var p pin
	info, err := os.Lstat(name)
	if err != nil {
		return p, err
	}
	if !info.Mode().IsRegular() || info.Size() > 2048 {
		return p, errors.New("invalid lock file")
	}
	body, err := os.ReadFile(name)
	if err != nil {
		return p, err
	}
	if err = json.Unmarshal(body, &p); err != nil {
		return p, err
	}
	if filepath.Base(name) != p.Slug+".json" || !idPattern.MatchString(p.Slug) || !verPattern.MatchString(p.Version) || !hashPattern.MatchString(p.SHA256) {
		return p, errors.New("invalid package pin")
	}
	return p, nil
}

func sameDirectory(expected, actual string) error {
	info, err := os.Lstat(actual)
	if err != nil {
		return err
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("existing path %s is not an installed package", actual)
	}
	root, err := os.OpenRoot(actual)
	if err != nil {
		return err
	}
	defer root.Close()
	return filepath.WalkDir(expected, func(p string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return err
		}
		rel, err := filepath.Rel(expected, p)
		if err != nil {
			return err
		}
		installed, err := root.Lstat(rel)
		if err != nil || !installed.Mode().IsRegular() {
			return fmt.Errorf("existing %s differs from registry source", actual)
		}
		a, err := os.ReadFile(p)
		if err != nil {
			return err
		}
		other, err := root.Open(rel)
		if err != nil {
			return err
		}
		b, err := io.ReadAll(io.LimitReader(other, int64(len(a))+1))
		other.Close()
		if err != nil || !bytes.Equal(a, b) {
			return fmt.Errorf("%s has local changes", filepath.Join(actual, rel))
		}
		return nil
	})
}

func (r *registry) install(slug, ver string, wanted *pin, demo bool) error {
	m, v, err := r.resolve(slug, ver)
	if err != nil {
		return err
	}
	p := pin{slug, v.Version, v.SHA256}
	if wanted != nil && p != *wanted {
		return errors.New("registry release differs from the project lock")
	}
	stage, err := os.MkdirTemp(".", ".nest-stage-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(stage)
	if err = r.unpack(slug, m.Module, v, stage); err != nil {
		return err
	}
	if demo {
		target := slug + "-demo"
		if _, err = os.Lstat(target); !os.IsNotExist(err) {
			return fmt.Errorf("%s already exists or cannot be inspected", target)
		}
		if err = os.Rename(stage, target); err != nil {
			return err
		}
		fmt.Printf("Run: blyxc native-run %s/main.blyx\n", target)
		return nil
	}
	base := "."
	if _, err = os.Stat("main.blyx"); os.IsNotExist(err) {
		if info, err := os.Lstat("src"); err == nil && info.IsDir() {
			if f, err := os.Stat(filepath.Join("src", "main.blyx")); err == nil && f.Mode().IsRegular() {
				base = "src"
			}
		}
	}
	vendor := filepath.Join(base, "vendor")
	if err = directory(vendor); err != nil {
		return err
	}
	target := filepath.Join(vendor, slug)
	source := filepath.Join(stage, "vendor", slug)
	_, err = os.Lstat(target)
	exists := err == nil
	if exists {
		if err = sameDirectory(source, target); err != nil {
			return err
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	if err = savePin("nest.lock", p); err != nil {
		return err
	}
	if !exists {
		if err = os.Rename(source, target); err != nil {
			if check := sameDirectory(source, target); check != nil {
				return err
			}
		}
	}
	fmt.Printf("%s@%s  use vendor::%s::%s;\n", slug, v.Version, slug, m.Module)
	return nil
}

func (r *registry) restore() error {
	info, err := os.Lstat("nest.lock")
	if err != nil {
		return err
	}
	if !info.IsDir() {
		return errors.New("nest.lock must be a directory")
	}
	entries, err := os.ReadDir("nest.lock")
	if err != nil {
		return err
	}
	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}
		p, err := readPin(filepath.Join("nest.lock", entry.Name()))
		if err != nil {
			return err
		}
		if err = r.install(p.Slug, p.Version, &p, false); err != nil {
			return err
		}
	}
	return nil
}

func (r *registry) search(query string) error {
	b, err := r.get("api/v1/index.json", 4<<20)
	if err != nil {
		return err
	}
	var index struct{ Packages, Tools []item }
	if err = json.Unmarshal(b, &index); err != nil {
		return err
	}
	all := append(index.Packages, index.Tools...)
	sort.Slice(all, func(i, j int) bool { return all[i].Slug < all[j].Slug })
	for _, p := range all {
		if strings.Contains(strings.ToLower(strings.Join([]string{p.Slug, p.Title, p.Kind, p.Description}, " ")), strings.ToLower(query)) {
			fmt.Printf("%s\t%s\t%s\t%s\n", p.Slug, p.Latest, p.Kind, p.Description)
		}
	}
	return nil
}

const usage = "nest search [terms] | info ID | add ID[@VERSION] | install | demo ID[@VERSION] | --version"

func run(args []string) error {
	if len(args) == 0 || args[0] == "--help" || args[0] == "help" {
		fmt.Println(usage)
		return nil
	}
	if len(args) == 1 && args[0] == "--version" {
		fmt.Println("nest " + version)
		return nil
	}
	r, err := registryClient()
	if err != nil {
		return err
	}
	if args[0] == "search" {
		return r.search(strings.Join(args[1:], " "))
	}
	if args[0] == "install" && len(args) == 1 {
		return r.restore()
	}
	if len(args) != 2 {
		return errors.New(usage)
	}
	slug, ver, err := spec(args[1])
	if err != nil {
		return err
	}
	switch args[0] {
	case "info":
		if slug == "nest" || slug == "blyxc" {
			if ver != "" {
				return errors.New("omit the version when looking up tool downloads")
			}
			b, err := r.get("api/v1/tools/"+slug+".json", 1<<20)
			if err != nil {
				return err
			}
			var tool struct{ Title, Latest, Description, Release string }
			if err = json.Unmarshal(b, &tool); err != nil {
				return err
			}
			fmt.Printf("%s %s\n%s\n%s\n", tool.Title, tool.Latest, tool.Description, tool.Release)
			return nil
		}
		m, v, err := r.resolve(slug, ver)
		if err != nil {
			return err
		}
		fmt.Printf("%s %s\n%s\nSHA-256 %s\n", m.Title, v.Version, m.Description, v.SHA256)
		return nil
	case "add", "demo":
		if slug == "nest" || slug == "blyxc" {
			return fmt.Errorf("use nest info %s for this tool's downloads", slug)
		}
		return r.install(slug, ver, nil, args[0] == "demo")
	}
	return errors.New(usage)
}

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, "nest:", err)
		os.Exit(1)
	}
}
