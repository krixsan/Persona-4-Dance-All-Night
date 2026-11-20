/* Kernel semaphores: 32-bit IDs, counted tokens and FIFO waiters.
 * Priority-ordered semaphores are approximated by FIFO order. */
#define _GNU_SOURCE
#include "runtime.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <errno.h>
#include <limits.h>
#include <time.h>
#define ERR(n) ((int32_t)(UINT32_C(0x80020000)|(n)))
typedef struct Waiter {
    int32_t need, result;
    int done;
    pthread_cond_t event;
    struct Waiter *next;
} Waiter;
typedef struct Sema {
    uint32_t id, attr;
    int32_t count, initial, maximum;
    unsigned active;
    int deleted;
    Waiter *first;
    struct Sema *next;
} Sema;
typedef struct PosixSema {
    const void *address;
    unsigned value, waiters;
    pthread_cond_t event;
    struct PosixSema *next;
} PosixSema;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static Sema *registry;
static PosixSema *posix_registry;
static uint32_t next_id=1;
static size_t created, deleted, acquired, signaled, timed_out;
static Sema *find(uint32_t id) {
    for (Sema *s=registry;s;s=s->next) if (s->id==id) return s;
    return NULL;
}
static PosixSema *find_posix(const void *address) {
    for (PosixSema *s=posix_registry;s;s=s->next) if (s->address==address) return s;
    return NULL;
}
static void host_check(int e) {
    if (e) { fprintf(stderr,"STOP: semaphore host error %d\n",e); exit(21); }
}
/* Waits use this clock for their deadlines. winpthreads condition variables accept only
 * CLOCK_REALTIME (pthread_condattr_setclock(CLOCK_MONOTONIC) fails with EINVAL). */
#ifdef _WIN32
#define WAIT_CLOCK CLOCK_REALTIME
#else
#define WAIT_CLOCK CLOCK_MONOTONIC
#endif
static uint64_t now_ns(void) {
    struct timespec t;
    if (clock_gettime(WAIT_CLOCK,&t)) { perror("clock_gettime"); exit(1); }
    return (uint64_t)t.tv_sec*1000000000+(uint64_t)t.tv_nsec;
}
static ABI int32_t sem_create(uint32_t *out,const char *name,uint32_t attr,
                              int32_t initial,int32_t maximum,const void *options) {
    if (!out || !name || attr>2 || initial<0 || maximum<=0 || initial>maximum) return ERR(22);
    if (options) { fputs("STOP: semaphore options are not implemented\n",stderr); exit(21); }
    Sema *s=calloc(1,sizeof(*s));
    if (!s) return ERR(12);
    pthread_mutex_lock(&lock);
    if (next_id==UINT32_MAX) { pthread_mutex_unlock(&lock); free(s); return ERR(28); }
    s->id=next_id++; s->attr=attr; s->count=s->initial=initial; s->maximum=maximum;
    s->next=registry; registry=s; *out=s->id; ++created;
    printf("Runtime: semaphore id=%u, attr=%u, initial=%d, max=%d\n",s->id,attr,initial,maximum);
    pthread_mutex_unlock(&lock);
    return 0;
}
static int32_t wait_count(uint32_t id,int32_t need,uint32_t *timeout,int block) {
    pthread_mutex_lock(&lock);
    Sema *s=find(id);
    int32_t result=0;
    if (!s) result=ERR(3);
    else if (need<=0 || need>s->maximum) result=ERR(22);
    else if (s->count>=need) { s->count-=need; ++acquired; }
    else if (!block) result=ERR(16);
    else if (timeout && !*timeout) { result=ERR(60); ++timed_out; }
    else {
        /* Priority-ordered semaphores (attr 2) are served FIFO: there is no
           PS4 priority scheduler, host threads run at equal priority. */
        if (getenv("BB_TRACE_SEMA")) fprintf(stderr,"Runtime: blocking wait on semaphore %u (need %d, count %d)\n",id,need,s->count); /* deadlock diagnosis */
        Waiter w={.need=need};
        pthread_condattr_t attr;
        host_check(pthread_condattr_init(&attr));
        host_check(pthread_condattr_setclock(&attr,WAIT_CLOCK));
        host_check(pthread_cond_init(&w.event,&attr));
        host_check(pthread_condattr_destroy(&attr));
        Waiter **tail=&s->first;
        while (*tail) tail=&(*tail)->next;
        *tail=&w; ++s->active;
        const uint64_t wait_start=runtime_wait_clock();
        uint64_t deadline=timeout ? now_ns()+(uint64_t)*timeout*1000 : 0;
        struct timespec end={.tv_sec=(time_t)(deadline/1000000000),.tv_nsec=(long)(deadline%1000000000)};
        while (!w.done) {
            int e=timeout ? pthread_cond_timedwait(&w.event,&lock,&end) : pthread_cond_wait(&w.event,&lock);
            if (e==ETIMEDOUT && !w.done) {
                Waiter **p=&s->first;
                while (*p!=&w) p=&(*p)->next;
                *p=w.next; w.result=ERR(60); w.done=1; ++timed_out;
            } else if (e!=ETIMEDOUT) host_check(e);
        }
        runtime_wait_note(2,runtime_wait_clock()-wait_start);
        result=w.result;
        if (!result) ++acquired;
        if (timeout) {
            uint64_t now=now_ns();
            *timeout=result ? 0 : (uint32_t)(now>=deadline ? 0 : (deadline-now)/1000);
        }
        host_check(pthread_cond_destroy(&w.event));
        if (!--s->active && s->deleted) free(s);
    }
    pthread_mutex_unlock(&lock);
    return result;
}
static ABI int32_t sem_wait(uint32_t id,int32_t need,uint32_t *timeout) { return wait_count(id,need,timeout,1); }
static ABI int32_t sem_poll(uint32_t id,int32_t need) { return wait_count(id,need,NULL,0); }
static ABI int32_t sem_signal(uint32_t id,int32_t count) {
    pthread_mutex_lock(&lock);
    Sema *s=find(id);
    int32_t result=0;
    if (!s) result=ERR(3);
    else if (count<=0 || count>s->maximum-s->count) result=ERR(22);
    else {
        s->count+=count; ++signaled;
        Waiter **p=&s->first;
        while (*p) {
            Waiter *w=*p;
            if (w->need>s->count) { p=&w->next; continue; }
            s->count-=w->need; *p=w->next; w->done=1;
            host_check(pthread_cond_signal(&w->event));
        }
    }
    pthread_mutex_unlock(&lock);
    return result;
}
static int32_t wake_all(Sema *s,int32_t result) {
    int32_t count=0;
    while (s->first) {
        Waiter *w=s->first; s->first=w->next;
        w->result=result; w->done=1; ++count;
        host_check(pthread_cond_signal(&w->event));
    }
    return count;
}
static ABI int32_t sem_cancel(uint32_t id,int32_t count,int32_t *waiters) {
    pthread_mutex_lock(&lock);
    Sema *s=find(id);
    int32_t result=0;
    if (!s) result=ERR(3);
    else if (count>s->maximum) result=ERR(22);
    else {
        int32_t n=wake_all(s,ERR(85));
        if (waiters) *waiters=n;
        s->count=count<0 ? s->initial : count;
    }
    pthread_mutex_unlock(&lock);
    return result;
}
static ABI int32_t sem_delete(uint32_t id) {
    pthread_mutex_lock(&lock);
    Sema **p=&registry;
    while (*p && (*p)->id!=id) p=&(*p)->next;
    if (!*p) { pthread_mutex_unlock(&lock); return ERR(3); }
    Sema *s=*p; *p=s->next; s->deleted=1; ++deleted;
    wake_all(s,ERR(13));
    if (!s->active) free(s);
    pthread_mutex_unlock(&lock);
    return 0;
}
/* Read-only test/diagnostic snapshot, not exposed to guest code. */
unsigned runtime_sema_waiters(uint32_t id) {
    pthread_mutex_lock(&lock);
    Sema *s=find(id); unsigned n=0;
    if (s) for (Waiter *w=s->first;w;w=w->next) ++n;
    pthread_mutex_unlock(&lock);
    return n;
}
static ABI int32_t posix_sem_init(void *address,int32_t pshared,uint32_t value) {
    if (!address || value>INT_MAX) { *runtime_errno()=EINVAL; return -1; }
    if (pshared) { *runtime_errno()=ENOSYS; return -1; }
    PosixSema *s=calloc(1,sizeof(*s));
    if (!s) { *runtime_errno()=ENOMEM; return -1; }
    const int e=pthread_cond_init(&s->event,NULL);
    if (e) { free(s); *runtime_errno()=e; return -1; }
    s->address=address; s->value=value;
    pthread_mutex_lock(&lock);
    if (find_posix(address)) {
        pthread_mutex_unlock(&lock);
        pthread_cond_destroy(&s->event);
        free(s);
        *runtime_errno()=EBUSY;
        return -1;
    }
    s->next=posix_registry; posix_registry=s;
    pthread_mutex_unlock(&lock);
    return 0;
}
static ABI int32_t posix_sem_destroy(void *address) {
    pthread_mutex_lock(&lock);
    PosixSema **p=&posix_registry;
    while (*p && (*p)->address!=address) p=&(*p)->next;
    if (!*p) { pthread_mutex_unlock(&lock); *runtime_errno()=EINVAL; return -1; }
    PosixSema *s=*p;
    if (s->waiters) { pthread_mutex_unlock(&lock); *runtime_errno()=EBUSY; return -1; }
    *p=s->next;
    pthread_mutex_unlock(&lock);
    const int e=pthread_cond_destroy(&s->event);
    free(s);
    if (e) { *runtime_errno()=e; return -1; }
    return 0;
}
static ABI int32_t posix_sem_wait(void *address) {
    pthread_mutex_lock(&lock);
    PosixSema *s=find_posix(address);
    if (!s) { pthread_mutex_unlock(&lock); *runtime_errno()=EINVAL; return -1; }
    ++s->waiters;
    while (!s->value) {
        const int e=pthread_cond_wait(&s->event,&lock);
        if (e) {
            --s->waiters;
            pthread_mutex_unlock(&lock);
            *runtime_errno()=e;
            return -1;
        }
    }
    --s->waiters;
    --s->value;
    pthread_mutex_unlock(&lock);
    return 0;
}
static ABI int32_t posix_sem_post(void *address) {
    pthread_mutex_lock(&lock);
    PosixSema *s=find_posix(address);
    if (!s) { pthread_mutex_unlock(&lock); *runtime_errno()=EINVAL; return -1; }
    if (s->value==INT_MAX) { pthread_mutex_unlock(&lock); *runtime_errno()=EOVERFLOW; return -1; }
    ++s->value;
    const int e=s->waiters ? pthread_cond_signal(&s->event) : 0;
    if (e) --s->value;
    pthread_mutex_unlock(&lock);
    if (e) { *runtime_errno()=e; return -1; }
    return 0;
}
static ABI int32_t posix_sem_getvalue(void *address,int32_t *value) {
    if (!value) { *runtime_errno()=EINVAL; return -1; }
    pthread_mutex_lock(&lock);
    PosixSema *s=find_posix(address);
    if (!s) { pthread_mutex_unlock(&lock); *runtime_errno()=EINVAL; return -1; }
    *value=(int32_t)s->value;
    pthread_mutex_unlock(&lock);
    return 0;
}
uintptr_t runtime_sema_resolve(const char *name) {
    if (runtime_nid_equals(name,"188x57JYp0g#libkernel")) return (uintptr_t)sem_create;
    if (runtime_nid_equals(name,"Zxa0VhQVTsk#libkernel")) return (uintptr_t)sem_wait;
    if (runtime_nid_equals(name,"4czppHBiriw#libkernel")) return (uintptr_t)sem_signal;
    if (runtime_nid_equals(name,"12wOHk8ywb0#libkernel")) return (uintptr_t)sem_poll;
    if (runtime_nid_equals(name,"4DM06U2BNEY#libkernel")) return (uintptr_t)sem_cancel;
    if (runtime_nid_equals(name,"R1Jvn8bSCW8#libkernel")) return (uintptr_t)sem_delete;
    if (runtime_nid_equals(name,"pDuPEf3m4fI#libScePosix")) return (uintptr_t)posix_sem_init;
    if (runtime_nid_equals(name,"cDW233RAwWo#libScePosix")) return (uintptr_t)posix_sem_destroy;
    if (runtime_nid_equals(name,"YCV5dGGBcCo#libScePosix")) return (uintptr_t)posix_sem_wait;
    if (runtime_nid_equals(name,"IKP8typ0QUk#libScePosix")) return (uintptr_t)posix_sem_post;
    if (runtime_nid_equals(name,"Bq+LRV-N6Hk#libScePosix")) return (uintptr_t)posix_sem_getvalue;
    return 0;
}
void runtime_sema_report(void) {
    pthread_mutex_lock(&lock);
    printf("Runtime: semaphores created=%zu, deleted=%zu, acquired=%zu, signals=%zu, timeouts=%zu\n",
           created,deleted,acquired,signaled,timed_out);
    pthread_mutex_unlock(&lock);
}
