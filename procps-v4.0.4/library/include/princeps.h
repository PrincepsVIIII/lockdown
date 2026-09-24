#ifndef PROCPS_PRINCEPS_H
#define PROCPS_PRINCEPS_H

#include <stddef.h>

void procps_princeps_reveal(int enabled);
int procps_princeps_mark(const char *target, char *err, size_t errlen);

#ifndef proc_t
struct proc_t;
int procps_princeps_filter_active(void);
int procps_princeps_hidden(const struct proc_t *p);
#endif

#endif
