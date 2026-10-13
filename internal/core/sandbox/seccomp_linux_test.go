//go:build linux

package sandbox

import "testing"

func TestDefaultAgentSyscallsIncludeNodeRuntimePrimitives(t *testing.T) {
	allowed := make(map[string]struct{})
	for _, name := range defaultAgentSyscalls() {
		allowed[name] = struct{}{}
	}

	// Modern Node/libuv needs clone3 for worker creation, epoll_pwait for its
	// event loop, madvise while initializing V8, and getsockopt to complete a
	// nonblocking socket connection. Returning EPERM for these calls causes
	// native assertions, a segmentation fault, or an opaque connection error.
	for _, name := range []string{"clone3", "epoll_pwait", "madvise", "getsockopt"} {
		if _, ok := allowed[name]; !ok {
			t.Errorf("default agent syscall allowlist is missing %q", name)
		}
		if _, ok := syscallNumber(name); !ok {
			t.Errorf("syscall table is missing %q", name)
		}
	}
}
