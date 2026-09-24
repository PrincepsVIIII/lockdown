#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdarg.h>

#include <sys/stat.h>
#include <sys/types.h>

#include "c.h"
#include "readproc.h"
#include "princeps.h"

#define PRINCEPS_STATE_FILE "/run/procps-princeps.state"

enum princeps_kind {
    PRINCEPS_PID,
    PRINCEPS_EXE,
    PRINCEPS_COMM
};

struct princeps_rule {
    struct princeps_rule *next;
    enum princeps_kind kind;
    pid_t pid;
    unsigned long long start_time;
    char *text;
};

static struct princeps_rule *rules;
static time_t rules_mtime;
static off_t rules_size = -1;
static int reveal_enabled;

static void set_error(char *err, size_t errlen, const char *msg)
{
    if (err && errlen)
        snprintf(err, errlen, "%s", msg);
}

static void clear_rules(void)
{
    struct princeps_rule *rule = rules;

    while (rule) {
        struct princeps_rule *next = rule->next;
        free(rule->text);
        free(rule);
        rule = next;
    }
    rules = NULL;
}

static char *trim(char *s)
{
    char *end;

    while (isspace((unsigned char)*s))
        ++s;
    end = s + strlen(s);
    while (end > s && isspace((unsigned char)end[-1]))
        *--end = '\0';
    return s;
}

static int parse_pid(const char *s, pid_t *pid)
{
    char *end = NULL;
    unsigned long value;

    if (!s || !*s)
        return 0;
    value = strtoul(s, &end, 10);
    if (!end || *end || value < 1 || value > INT_MAX)
        return 0;
    *pid = (pid_t)value;
    return 1;
}

static int read_start_time(pid_t pid, unsigned long long *start_time)
{
    char path[64], buf[4096], *end;
    FILE *fp;
    char state;
    int ppid, pgrp, session, tty, tpgid, priority, nice, nlwp;
    unsigned long flags, min_flt, cmin_flt, maj_flt, cmaj_flt, alarm;
    unsigned long long utime, stime, cutime, cstime, start;

    snprintf(path, sizeof(path), "/proc/%ld/stat", (long)pid);
    fp = fopen(path, "r");
    if (!fp)
        return -1;
    if (!fgets(buf, sizeof(buf), fp)) {
        fclose(fp);
        return -1;
    }
    fclose(fp);

    end = strrchr(buf, ')');
    if (!end || !end[1])
        return -1;
    end += 2;

    if (sscanf(end,
            "%c %d %d %d %d %d %lu %lu %lu %lu %lu "
            "%llu %llu %llu %llu %d %d %d %lu %llu",
            &state, &ppid, &pgrp, &session, &tty, &tpgid,
            &flags, &min_flt, &cmin_flt, &maj_flt, &cmaj_flt,
            &utime, &stime, &cutime, &cstime,
            &priority, &nice, &nlwp, &alarm, &start) != 20)
        return -1;

    *start_time = start;
    return 0;
}

static int append_rule(const char *fmt, ...)
{
    va_list ap;
    int fd, ret;
    FILE *fp;

    fd = open(PRINCEPS_STATE_FILE, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0644);
    if (fd < 0)
        return -1;
    (void)fchmod(fd, 0644);
    fp = fdopen(fd, "a");
    if (!fp) {
        close(fd);
        return -1;
    }

    va_start(ap, fmt);
    ret = vfprintf(fp, fmt, ap);
    va_end(ap);
    if (fclose(fp) != 0)
        return -1;

    rules_size = -1;
    return ret < 0 ? -1 : 0;
}

static int add_loaded_rule(enum princeps_kind kind, pid_t pid,
        unsigned long long start_time, const char *text)
{
    struct princeps_rule *rule = calloc(1, sizeof(*rule));

    if (!rule)
        return -1;
    rule->kind = kind;
    rule->pid = pid;
    rule->start_time = start_time;
    if (text && !(rule->text = strdup(text))) {
        free(rule);
        return -1;
    }
    rule->next = rules;
    rules = rule;
    return 0;
}

static void load_rules(void)
{
    struct stat st;
    FILE *fp;
    char line[PATH_MAX + 128];

    if (stat(PRINCEPS_STATE_FILE, &st) != 0) {
        clear_rules();
        rules_mtime = 0;
        rules_size = -1;
        return;
    }
    if (rules_size == st.st_size && rules_mtime == st.st_mtime)
        return;

    clear_rules();
    rules_mtime = st.st_mtime;
    rules_size = st.st_size;

    fp = fopen(PRINCEPS_STATE_FILE, "r");
    if (!fp)
        return;

    while (fgets(line, sizeof(line), fp)) {
        char *kind = trim(line);
        char *arg = strchr(kind, ' ');

        if (!arg)
            continue;
        *arg++ = '\0';
        arg = trim(arg);

        if (!strcmp(kind, "pid")) {
            char *start = strchr(arg, ' ');
            pid_t pid;
            unsigned long long start_time;

            if (!start)
                continue;
            *start++ = '\0';
            start = trim(start);
            if (parse_pid(arg, &pid) && sscanf(start, "%llu", &start_time) == 1)
                add_loaded_rule(PRINCEPS_PID, pid, start_time, NULL);
        } else if (!strcmp(kind, "exe")) {
            if (*arg)
                add_loaded_rule(PRINCEPS_EXE, 0, 0, arg);
        } else if (!strcmp(kind, "comm")) {
            if (*arg)
                add_loaded_rule(PRINCEPS_COMM, 0, 0, arg);
        }
    }
    fclose(fp);
}

void procps_princeps_reveal(int enabled)
{
    reveal_enabled = enabled;
}

int procps_princeps_mark(const char *target, char *err, size_t errlen)
{
    pid_t pid;
    unsigned long long start_time;

    if (!target || !*target) {
        set_error(err, errlen, "missing --princeps-rule target");
        return -1;
    }

    if (parse_pid(target, &pid)) {
        if (read_start_time(pid, &start_time) != 0) {
            set_error(err, errlen, "could not read target process");
            return -1;
        }
        if (append_rule("pid %ld %llu\n", (long)pid, start_time) != 0) {
            set_error(err, errlen, "could not update princeps state");
            return -1;
        }
        return 0;
    }

    if (strchr(target, '/')) {
        char resolved[PATH_MAX];
        const char *path = target;

        if (realpath(target, resolved))
            path = resolved;
        if (append_rule("exe %s\n", path) != 0) {
            set_error(err, errlen, "could not update princeps state");
            return -1;
        }
    } else if (append_rule("comm %s\n", target) != 0) {
        set_error(err, errlen, "could not update princeps state");
        return -1;
    }
    return 0;
}

int procps_princeps_filter_active(void)
{
    struct stat st;

    if (reveal_enabled)
        return 0;
    if (stat(PRINCEPS_STATE_FILE, &st) != 0 || st.st_size <= 0) {
        clear_rules();
        rules_mtime = 0;
        rules_size = -1;
        return 0;
    }
    return 1;
}

static const char *base_name(const char *path)
{
    const char *slash;

    if (!path)
        return NULL;
    slash = strrchr(path, '/');
    return slash ? slash + 1 : path;
}

static int read_proc_exe(pid_t pid, char *buf, size_t buflen)
{
    char path[64];
    ssize_t len;

    snprintf(path, sizeof(path), "/proc/%ld/exe", (long)pid);
    len = readlink(path, buf, buflen - 1);
    if (len < 0)
        return -1;
    buf[len] = '\0';
    return 0;
}

int procps_princeps_hidden(const proc_t *p)
{
    struct princeps_rule *rule;

    if (!procps_princeps_filter_active() || !p)
        return 0;
    if (p->tgid == getpid() || p->tid == getpid())
        return 0;

    load_rules();
    for (rule = rules; rule; rule = rule->next) {
        switch (rule->kind) {
        case PRINCEPS_PID:
            if (p->tgid == rule->pid || p->tid == rule->pid) {
                if (p->tid != rule->pid || p->start_time == rule->start_time)
                    return 1;
            }
            break;
        case PRINCEPS_EXE:
        {
            char exe_buf[PATH_MAX];
            const char *exe = p->exe;
            int exe_available = exe != NULL;

            if (!exe && read_proc_exe(p->tgid, exe_buf, sizeof(exe_buf)) == 0) {
                exe = exe_buf;
                exe_available = 1;
            }
            if (exe_available && !strcmp(exe, rule->text))
                return 1;
            if (!exe_available && p->cmd && !strcmp(p->cmd, base_name(rule->text)))
                return 1;
            break;
        }
        case PRINCEPS_COMM:
            if (p->cmd && !strcmp(p->cmd, rule->text))
                return 1;
            break;
        }
    }
    return 0;
}
