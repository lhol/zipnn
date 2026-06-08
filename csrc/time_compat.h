/* Minimal gettimeofday compatibility for Windows */
#ifndef TIME_COMPAT_H
#define TIME_COMPAT_H

#ifdef _WIN32
#include <windows.h>
#include <stdint.h>

/* timeval should already be defined by Python.h via winsock.h on Windows.
   Just provide gettimeofday implementation.
*/

/* gettimeofday implementation for Windows using GetSystemTimeAsFileTime */
static inline int gettimeofday(struct timeval *tv, void *tz) {
    (void)tz;
    FILETIME ft;
    unsigned long long tmpres = 0;
    
    GetSystemTimeAsFileTime(&ft);
    tmpres |= ft.dwHighDateTime;
    tmpres <<= 32;
    tmpres |= ft.dwLowDateTime;

    /* Convert from 100-nanosecond intervals since January 1, 1601 to Unix epoch */
    tmpres -= 116444736000000000ULL;
    tmpres /= 10ULL; /* Convert to microseconds */

    tv->tv_sec = (long)(tmpres / 1000000ULL);
    tv->tv_usec = (long)(tmpres % 1000000ULL);
    return 0;
}

#endif /* _WIN32 */

#endif /* TIME_COMPAT_H */
