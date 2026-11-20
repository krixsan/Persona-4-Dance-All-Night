#define _GNU_SOURCE
#include "runtime.h"
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <ucontext.h>
#endif

#define FIBER_MAGIC_START UINT32_C(0xdef1649c)
#define FIBER_MAGIC_END UINT32_C(0xb37592a0)
#define FIBER_OPT_MAGIC UINT32_C(0xbb40e64d)
#define FIBER_MIN_CONTEXT 512
#define FIBER_DEFAULT_STACK (1024 * 1024)
#define FIBER_STATE_RUN 1
#define FIBER_STATE_IDLE 2
#define FIBER_STATE_TERMINATED 3
#define FIBER_ERR(n) ((int32_t)(UINT32_C(0x80590000) | (n)))
#define SCE_ENOMEM ((int32_t)UINT32_C(0x8002000c))

typedef void (ABI *FiberEntry)(uint64_t arg_on_initialize, uint64_t arg_on_run);

typedef struct RuntimeFiber {
    uint32_t magic_start;
    uint32_t state;
    FiberEntry entry;
    uint64_t arg_on_initialize;
    void *addr_context;
    uint64_t size_context;
    char name[32];
    void *context;
    uint32_t flags;
    void *context_start;
    void *context_end;
    uint32_t magic_end;
} RuntimeFiber;
_Static_assert(sizeof(RuntimeFiber) <= 256, "PS4 fiber control block exceeds its ABI limit");

typedef struct HostFiber {
    RuntimeFiber *guest;
    struct HostFiber *next;
    pthread_t owner;
    int owner_set;
    int context_ready;
    uint64_t incoming;
    uint64_t return_value;
#ifdef _WIN32
    void *native;
#else
    ucontext_t context;
    void *owned_stack;
#endif
} HostFiber;

static pthread_mutex_t fibers_lock = PTHREAD_MUTEX_INITIALIZER;
static HostFiber *fibers;
static _Thread_local struct {
    HostFiber *current;
    void *thread_fiber;
    int run_active;
    uint64_t return_value;
#ifndef _WIN32
    ucontext_t thread_context;
#endif
} thread_state;

static int32_t fiber_error(unsigned error) { return FIBER_ERR(error); }

static HostFiber *find_fiber(const RuntimeFiber *guest) {
    HostFiber *found = NULL;
    pthread_mutex_lock(&fibers_lock);
    for (HostFiber *fiber = fibers; fiber; fiber = fiber->next) {
        if (fiber->guest == guest) {
            found = fiber;
            break;
        }
    }
    pthread_mutex_unlock(&fibers_lock);
    return found;
}

#ifdef _WIN32
static VOID WINAPI fiber_trampoline(void *parameter);
#else
static void fiber_trampoline(void);
#endif

static int32_t prepare_fiber(HostFiber *fiber) {
    if (fiber->owner_set) {
        return pthread_equal(fiber->owner, pthread_self()) ? 0 : fiber_error(5);
    }
    fiber->owner = pthread_self();
    fiber->owner_set = 1;
#ifdef _WIN32
    SIZE_T stack_size = fiber->guest->size_context
        ? (SIZE_T)fiber->guest->size_context : FIBER_DEFAULT_STACK;
    if (stack_size < 64 * 1024) stack_size = 64 * 1024;
    /* shortcut: Windows owns the fiber stack, upgrade if guest stack identity is required. */
    fiber->native = CreateFiberEx(0, stack_size, FIBER_FLAG_FLOAT_SWITCH,
                                  fiber_trampoline, fiber);
    if (!fiber->native) {
        fiber->owner_set = 0;
        return SCE_ENOMEM;
    }
#else
    if (getcontext(&fiber->context) != 0) {
        fiber->owner_set = 0;
        return SCE_ENOMEM;
    }
    if (fiber->guest->addr_context) {
        fiber->context.uc_stack.ss_sp = fiber->guest->addr_context;
        fiber->context.uc_stack.ss_size = (size_t)fiber->guest->size_context;
    } else {
        fiber->owned_stack = malloc(FIBER_DEFAULT_STACK);
        if (!fiber->owned_stack) {
            fiber->owner_set = 0;
            return SCE_ENOMEM;
        }
        fiber->context.uc_stack.ss_sp = fiber->owned_stack;
        fiber->context.uc_stack.ss_size = FIBER_DEFAULT_STACK;
    }
    fiber->context.uc_stack.ss_flags = 0;
    fiber->context.uc_link = &thread_state.thread_context;
    makecontext(&fiber->context, fiber_trampoline, 0);
#endif
    fiber->context_ready = 1;
    return 0;
}

#ifdef _WIN32
static int ensure_thread_fiber(void) {
    if (thread_state.thread_fiber) return 1;
    if (IsThreadAFiber()) {
        thread_state.thread_fiber = GetCurrentFiber();
    } else {
        thread_state.thread_fiber = ConvertThreadToFiberEx(NULL, FIBER_FLAG_FLOAT_SWITCH);
    }
    return thread_state.thread_fiber != NULL;
}

static void switch_to_thread(void) {
    SwitchToFiber(thread_state.thread_fiber);
}

static VOID WINAPI fiber_trampoline(void *parameter) {
    HostFiber *fiber = parameter;
    thread_state.current = fiber;
    fiber->guest->entry(fiber->guest->arg_on_initialize, fiber->incoming);
    fiber->guest->state = FIBER_STATE_TERMINATED;
    thread_state.return_value = 0;
    thread_state.current = NULL;
    switch_to_thread();
    abort();
}
#else
static void fiber_trampoline(void) {
    HostFiber *fiber = thread_state.current;
    fiber->guest->entry(fiber->guest->arg_on_initialize, fiber->incoming);
    fiber->guest->state = FIBER_STATE_TERMINATED;
    thread_state.return_value = 0;
    thread_state.current = NULL;
}

static int switch_context(ucontext_t *from, ucontext_t *to) {
    return swapcontext(from, to) == 0;
}
#endif

static ABI int32_t initialize_fiber(RuntimeFiber *guest, const char *name, FiberEntry entry,
                                    uint64_t arg_on_initialize, void *addr_context,
                                    uint64_t size_context, const uint32_t *opt_param,
                                    uint32_t flags, uint32_t build_version) {
    (void)build_version;
    if (!guest || !name || !entry) return fiber_error(1);
    if ((uintptr_t)guest & 7 || ((uintptr_t)addr_context & 15))
        return fiber_error(2);
    if (opt_param && ((uintptr_t)opt_param & 7)) return fiber_error(2);
    if (size_context && size_context < FIBER_MIN_CONTEXT) return fiber_error(3);
    if (size_context & 15) return fiber_error(4);
    if ((!addr_context) != (!size_context)) return fiber_error(4);
    if (size_context > SIZE_MAX ||
        (addr_context && (uintptr_t)addr_context > UINTPTR_MAX - (uintptr_t)size_context))
        return fiber_error(3);
    if (opt_param && *opt_param != FIBER_OPT_MAGIC) return fiber_error(4);

    pthread_mutex_lock(&fibers_lock);
    for (HostFiber *it = fibers; it; it = it->next) {
        if (it->guest == guest) {
            pthread_mutex_unlock(&fibers_lock);
            return fiber_error(6);
        }
    }
    HostFiber *fiber = calloc(1, sizeof(*fiber));
    if (!fiber) {
        pthread_mutex_unlock(&fibers_lock);
        return SCE_ENOMEM;
    }
    memset(guest, 0, sizeof(*guest));
    guest->magic_start = FIBER_MAGIC_START;
    guest->state = FIBER_STATE_IDLE;
    guest->entry = entry;
    guest->arg_on_initialize = arg_on_initialize;
    guest->addr_context = addr_context;
    guest->size_context = size_context;
    guest->flags = flags;
    guest->context_start = addr_context;
    guest->context_end = addr_context ? (unsigned char *)addr_context + size_context : NULL;
    strncpy(guest->name, name, sizeof(guest->name) - 1);
    guest->magic_end = FIBER_MAGIC_END;
    fiber->guest = guest;
    fiber->next = fibers;
    fibers = fiber;
    pthread_mutex_unlock(&fibers_lock);
    return 0;
}

static ABI int32_t finalize_fiber(RuntimeFiber *guest) {
    if (!guest) return fiber_error(1);
    if ((uintptr_t)guest & 7) return fiber_error(2);
    pthread_mutex_lock(&fibers_lock);
    HostFiber **link = &fibers;
    while (*link && (*link)->guest != guest) link = &(*link)->next;
    HostFiber *fiber = *link;
    if (!fiber || guest->magic_start != FIBER_MAGIC_START ||
        guest->magic_end != FIBER_MAGIC_END) {
        pthread_mutex_unlock(&fibers_lock);
        return fiber_error(4);
    }
    if (guest->state != FIBER_STATE_IDLE) {
        pthread_mutex_unlock(&fibers_lock);
        return fiber_error(6);
    }
    if (fiber->owner_set && !pthread_equal(fiber->owner, pthread_self())) {
        pthread_mutex_unlock(&fibers_lock);
        return fiber_error(5);
    }
    *link = fiber->next;
    guest->state = FIBER_STATE_TERMINATED;
    pthread_mutex_unlock(&fibers_lock);
#ifdef _WIN32
    if (fiber->native) DeleteFiber(fiber->native);
#else
    free(fiber->owned_stack);
#endif
    free(fiber);
    return 0;
}

static ABI int32_t run_fiber(RuntimeFiber *guest, uint64_t arg_on_run_to,
                             uint64_t *arg_on_return) {
    if (!guest) return fiber_error(1);
    if ((uintptr_t)guest & 7) return fiber_error(2);
    HostFiber *fiber = find_fiber(guest);
    if (!fiber || guest->magic_start != FIBER_MAGIC_START ||
        guest->magic_end != FIBER_MAGIC_END) return fiber_error(4);
    if (thread_state.run_active) return fiber_error(5);
    if (guest->state != FIBER_STATE_IDLE) return fiber_error(6);
#ifdef _WIN32
    if (!ensure_thread_fiber()) return SCE_ENOMEM;
#endif
    int32_t result = fiber->context_ready ? 0 : prepare_fiber(fiber);
    if (result) return result;
    if (fiber->owner_set && !pthread_equal(fiber->owner, pthread_self()))
        return fiber_error(5);
    fiber->incoming = arg_on_run_to;
    fiber->guest->state = FIBER_STATE_RUN;
    thread_state.current = fiber;
    thread_state.run_active = 1;
    thread_state.return_value = 0;
#ifdef _WIN32
    SwitchToFiber(fiber->native);
#else
    if (!switch_context(&thread_state.thread_context, &fiber->context)) {
        thread_state.current = NULL;
        thread_state.run_active = 0;
        guest->state = FIBER_STATE_IDLE;
        return SCE_ENOMEM;
    }
#endif
    thread_state.current = NULL;
    thread_state.run_active = 0;
    if (arg_on_return) *arg_on_return = thread_state.return_value;
    return 0;
}

static ABI int32_t switch_fiber(RuntimeFiber *guest, uint64_t arg_on_run_to,
                                uint64_t *arg_on_run) {
    if (!guest) return fiber_error(1);
    if ((uintptr_t)guest & 7) return fiber_error(2);
    HostFiber *target = find_fiber(guest);
    HostFiber *current = thread_state.current;
    if (!target || guest->magic_start != FIBER_MAGIC_START ||
        guest->magic_end != FIBER_MAGIC_END) return fiber_error(4);
    if (!current || !thread_state.run_active) return fiber_error(5);
    if (target == current || guest->state != FIBER_STATE_IDLE)
        return fiber_error(6);
    int32_t result = target->context_ready ? 0 : prepare_fiber(target);
    if (result) return result;
    if (target->owner_set && !pthread_equal(target->owner, pthread_self()))
        return fiber_error(5);

    current->guest->state = FIBER_STATE_IDLE;
    target->incoming = arg_on_run_to;
    target->guest->state = FIBER_STATE_RUN;
    thread_state.current = target;
#ifdef _WIN32
    SwitchToFiber(target->native);
#else
    if (!switch_context(&current->context, &target->context)) {
        thread_state.current = current;
        current->guest->state = FIBER_STATE_RUN;
        target->guest->state = FIBER_STATE_IDLE;
        return SCE_ENOMEM;
    }
#endif
    thread_state.current = current;
    current->guest->state = FIBER_STATE_RUN;
    if (arg_on_run) *arg_on_run = current->incoming;
    return 0;
}

static ABI int32_t get_self(RuntimeFiber **out) {
    if (!out) return fiber_error(1);
    if (!thread_state.current || !thread_state.run_active) return fiber_error(5);
    *out = thread_state.current->guest;
    return 0;
}

static ABI int32_t return_to_thread(uint64_t arg_on_return, uint64_t *arg_on_run) {
    HostFiber *fiber = thread_state.current;
    if (!fiber || !thread_state.run_active) return fiber_error(5);
    fiber->return_value = arg_on_return;
    fiber->guest->state = FIBER_STATE_IDLE;
    thread_state.return_value = arg_on_return;
    thread_state.current = NULL;
#ifdef _WIN32
    switch_to_thread();
#else
    if (!switch_context(&fiber->context, &thread_state.thread_context)) {
        thread_state.current = fiber;
        fiber->guest->state = FIBER_STATE_RUN;
        return SCE_ENOMEM;
    }
#endif
    thread_state.current = fiber;
    fiber->guest->state = FIBER_STATE_RUN;
    if (arg_on_run) *arg_on_run = fiber->incoming;
    return 0;
}

uintptr_t runtime_fiber_resolve(const char *name) {
    static const struct { const char *nid; void *function; } table[] = {
        {"hVYD7Ou2pCQ#libSceFiber", initialize_fiber},
        {"JeNX5F-NzQU#libSceFiber", finalize_fiber},
        {"p+zLIOg27zU#libSceFiber", get_self},
        {"B0ZX2hx9DMw#libSceFiber", return_to_thread},
        {"a0LLrZWac0M#libSceFiber", run_fiber},
        {"PFT2S-tJ7Uk#libSceFiber", switch_fiber},
    };
    for (size_t i = 0; i < sizeof(table) / sizeof(*table); ++i)
        if (runtime_nid_equals(name, table[i].nid))
            return (uintptr_t)table[i].function;
    return 0;
}
