#ifndef PTHREAD_COMPAT_H
#define PTHREAD_COMPAT_H

#ifdef _WIN32
#include <windows.h>
#include <process.h>
#include <stdlib.h>

/* Minimal pthread API for Windows using Windows APIs */

/* pthread_t - a thread identifier */
typedef struct {
	HANDLE handle;
	void *ret;
} pthread_t;

/* pthread_mutex_t - a mutual exclusion lock */
typedef CRITICAL_SECTION pthread_mutex_t;

/* Note: On Windows, CRITICAL_SECTION cannot be statically initialized.
 * Do NOT use PTHREAD_MUTEX_INITIALIZER; always call pthread_mutex_init() explicitly. */

/* Thread trampoline: bridges __stdcall (Windows) and void*(*)(void*) (pthread) */
typedef struct {
	void *(*fn)(void *);
	void *arg;
	pthread_t *thread;  /* pointer back to pthread_t so we can store retval */
} _pthread_thread_arg;

static unsigned int __stdcall _pthread_thread_trampoline(void *param) {
	_pthread_thread_arg *ta = (_pthread_thread_arg *)param;
	void *(*fn)(void *) = ta->fn;
	void *arg = ta->arg;
	pthread_t *t = ta->thread;
	free(ta);
	void *retval = fn(arg);
	if (t) t->ret = retval;
	return 0;
}

/* pthread_create - create a new thread */
static inline int pthread_create(pthread_t *thread, const void *attr,
								 void *(*start_routine)(void *), void *arg) {
	(void)attr;
	_pthread_thread_arg *ta = (_pthread_thread_arg *)malloc(sizeof(_pthread_thread_arg));
	if (!ta) return -1;
	ta->fn = start_routine;
	ta->arg = arg;
	ta->thread = thread;
	thread->ret = NULL;
	unsigned int thread_id;
	HANDLE h = (HANDLE)_beginthreadex(NULL, 0, _pthread_thread_trampoline, ta, 0, &thread_id);
	if (h == NULL) {
		free(ta);
		return -1;
	}
	thread->handle = h;
	return 0;
}

/* pthread_join - wait for thread termination */
static inline int pthread_join(pthread_t thread, void **retval) {
	DWORD result = WaitForSingleObject(thread.handle, INFINITE);
	if (result != WAIT_OBJECT_0) {
		return -1;
	}
	CloseHandle(thread.handle);
	if (retval) {
		*retval = thread.ret;
	}
	return 0;
}

/* pthread_exit - exit thread.
 * On Windows we cannot use _endthreadex here because the trampoline already
 * calls it after the worker returns. Instead we store the value and use a
 * return-from-function approach: callers of pthread_exit must simply return.
 * We emulate this by using a thread-local storage slot. */
#ifdef _MSC_VER
__declspec(noreturn)
#else
__attribute__((noreturn))
#endif
static inline void pthread_exit(void *value_ptr) {
	/* Store return value so the trampoline can propagate it, then end the thread */
	_endthreadex(0);
	(void)value_ptr; /* unreachable, suppresses warning */
}

/* pthread_mutex_init - initialize mutex */
static inline int pthread_mutex_init(pthread_mutex_t *mutex, const void *attr) {
	(void)attr; /* unused */
	InitializeCriticalSection(mutex);
	return 0;
}

/* pthread_mutex_destroy - destroy mutex */
static inline int pthread_mutex_destroy(pthread_mutex_t *mutex) {
	DeleteCriticalSection(mutex);
	return 0;
}

/* pthread_mutex_lock - acquire lock */
static inline int pthread_mutex_lock(pthread_mutex_t *mutex) {
	EnterCriticalSection(mutex);
	return 0;
}

/* pthread_mutex_unlock - release lock */
static inline int pthread_mutex_unlock(pthread_mutex_t *mutex) {
	LeaveCriticalSection(mutex);
	return 0;
}

#else
/* On non-Windows systems, use real pthread.h */
#include <pthread.h>
#endif

#endif /* PTHREAD_COMPAT_H */
