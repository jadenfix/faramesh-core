package artifactverify

import (
	"os"
	"path/filepath"
	"testing"
)

func TestVerifyManifest_ok(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "a.txt")
	if err := os.WriteFile(p, []byte("hello"), 0o600); err != nil {
		t.Fatal(err)
	}
	h, err := FileSHA256Hex(p)
	if err != nil {
		t.Fatal(err)
	}
	m := &ManifestV1{Version: 1, Artifacts: []ArtifactDigest{{Path: "a.txt", SHA256: h}}}
	if err := VerifyManifest(dir, m); err != nil {
		t.Fatal(err)
	}
}

func TestBuildManifestV1(t *testing.T) {
	dir := t.TempDir()
	a := filepath.Join(dir, "a.txt")
	b := filepath.Join(dir, "sub", "b.txt")
	if err := os.MkdirAll(filepath.Join(dir, "sub"), 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(a, []byte("x"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(b, []byte("y"), 0o600); err != nil {
		t.Fatal(err)
	}
	m, err := BuildManifestV1(dir, []string{a, b})
	if err != nil {
		t.Fatal(err)
	}
	if len(m.Artifacts) != 2 {
		t.Fatalf("len %d", len(m.Artifacts))
	}
	if err := VerifyManifest(dir, m); err != nil {
		t.Fatal(err)
	}
}

func TestVerifyManifest_mismatch(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "a.txt")
	if err := os.WriteFile(p, []byte("hello"), 0o600); err != nil {
		t.Fatal(err)
	}
	m := &ManifestV1{Version: 1, Artifacts: []ArtifactDigest{{Path: "a.txt", SHA256: "00"}}}
	if err := VerifyManifest(dir, m); err == nil {
		t.Fatal("expected error")
	}
}

func TestVerifyManifest_rejectsInvalidAndEscapingPaths(t *testing.T) {
	base := t.TempDir()
	outside := t.TempDir()
	secret := filepath.Join(outside, "secret.txt")
	if err := os.WriteFile(secret, []byte("outside"), 0o600); err != nil {
		t.Fatal(err)
	}
	h, err := FileSHA256Hex(secret)
	if err != nil {
		t.Fatal(err)
	}

	link := filepath.Join(base, "artifact.txt")
	if err := os.Symlink(secret, link); err != nil {
		t.Skipf("symlinks unavailable: %v", err)
	}

	tests := []string{"../secret.txt", secret, "artifact.txt"}
	for _, path := range tests {
		t.Run(path, func(t *testing.T) {
			m := &ManifestV1{Version: 1, Artifacts: []ArtifactDigest{{Path: path, SHA256: h}}}
			if err := VerifyManifest(base, m); err == nil {
				t.Fatalf("expected %q to be rejected", path)
			}
		})
	}
}

func TestBuildManifestV1_rejectsSymlinkOutsideBaseDir(t *testing.T) {
	base := t.TempDir()
	outside := filepath.Join(t.TempDir(), "outside.txt")
	if err := os.WriteFile(outside, []byte("outside"), 0o600); err != nil {
		t.Fatal(err)
	}
	link := filepath.Join(base, "artifact.txt")
	if err := os.Symlink(outside, link); err != nil {
		t.Skipf("symlinks unavailable: %v", err)
	}

	if _, err := BuildManifestV1(base, []string{link}); err == nil {
		t.Fatal("expected symlink escaping base-dir to be rejected")
	}
}

func TestVerifyManifest_allowsSymlinkWithinBaseDir(t *testing.T) {
	base := t.TempDir()
	target := filepath.Join(base, "target.txt")
	if err := os.WriteFile(target, []byte("inside"), 0o600); err != nil {
		t.Fatal(err)
	}
	link := filepath.Join(base, "artifact.txt")
	if err := os.Symlink(target, link); err != nil {
		t.Skipf("symlinks unavailable: %v", err)
	}
	h, err := FileSHA256Hex(target)
	if err != nil {
		t.Fatal(err)
	}
	m := &ManifestV1{Version: 1, Artifacts: []ArtifactDigest{{Path: "artifact.txt", SHA256: h}}}
	if err := VerifyManifest(base, m); err != nil {
		t.Fatalf("expected in-tree symlink to verify: %v", err)
	}
}
