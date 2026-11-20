#include "runtime.h"
#include <assert.h>
#include <stdint.h>

typedef int32_t (ABI *FiberInitialize)(void *, const char *, void (ABI *)(uint64_t, uint64_t),
                                      uint64_t, void *, uint64_t, const uint32_t *,
                                      uint32_t, uint32_t);
typedef int32_t (ABI *FiberFinalize)(void *);
typedef int32_t (ABI *FiberRun)(void *, uint64_t, uint64_t *);
typedef int32_t (ABI *FiberSwitch)(void *, uint64_t, uint64_t *);
typedef int32_t (ABI *FiberGetSelf)(void **);
typedef int32_t (ABI *FiberReturnToThread)(uint64_t, uint64_t *);

static FiberSwitch fiber_switch;
static FiberGetSelf fiber_get_self;
static FiberReturnToThread fiber_return_to_thread;
static void *fiber_a, *fiber_b;
static int entries;

static ABI void fiber_entry_b(uint64_t initial, uint64_t run) {
    assert(initial == 0xb1 && run == 0x22);
    void *self = NULL;
    assert(fiber_get_self(&self) == 0 && self == fiber_b);
    ++entries;
    assert(fiber_return_to_thread(0xb2, NULL) == 0);
}

static ABI void fiber_entry_a(uint64_t initial, uint64_t run) {
    assert(initial == 0xa1 && run == 0x11);
    void *self = NULL;
    assert(fiber_get_self(&self) == 0 && self == fiber_a);
    ++entries;
    uint64_t resumed = 0;
    assert(fiber_switch(fiber_b, 0x22, &resumed) == 0);
    assert(resumed == 0x33);
    assert(fiber_return_to_thread(0xa2, NULL) == 0);
}

int main(void) {
    FiberInitialize initialize = (FiberInitialize)runtime_fiber_resolve("hVYD7Ou2pCQ#libSceFiber");
    FiberFinalize finalize = (FiberFinalize)runtime_fiber_resolve("JeNX5F-NzQU#libSceFiber");
    FiberRun run = (FiberRun)runtime_fiber_resolve("a0LLrZWac0M#libSceFiber");
    fiber_switch = (FiberSwitch)runtime_fiber_resolve("PFT2S-tJ7Uk#libSceFiber");
    fiber_get_self = (FiberGetSelf)runtime_fiber_resolve("p+zLIOg27zU#libSceFiber");
    fiber_return_to_thread =
        (FiberReturnToThread)runtime_fiber_resolve("B0ZX2hx9DMw#libSceFiber");
    assert(initialize && finalize && run && fiber_switch && fiber_get_self &&
           fiber_return_to_thread);

    _Alignas(16) unsigned char storage_a[256], storage_b[256];
    _Alignas(16) unsigned char stack_a[64 * 1024], stack_b[64 * 1024];
    fiber_a = storage_a;
    fiber_b = storage_b;
    assert(initialize(fiber_a, "fiber-a", fiber_entry_a, 0xa1, stack_a,
                      sizeof(stack_a), NULL, 0, 0x04508001) == 0);
    assert(initialize(fiber_b, "fiber-b", fiber_entry_b, 0xb1, stack_b,
                      sizeof(stack_b), NULL, 0, 0x04508001) == 0);

    uint64_t returned = 0;
    assert(run(fiber_a, 0x11, &returned) == 0 && returned == 0xb2);
    assert(entries == 2);
    assert(run(fiber_a, 0x33, &returned) == 0 && returned == 0xa2);
    assert(finalize(fiber_a) == 0 && finalize(fiber_b) == 0);
    assert((uint32_t)fiber_get_self(&fiber_a) == 0x80590005);
    assert((uint32_t)run(fiber_a, 0, &returned) == 0x80590004);
    return 0;
}
