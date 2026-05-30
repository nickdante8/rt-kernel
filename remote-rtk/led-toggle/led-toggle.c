#define _GNU_SOURCE
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <syslog.h>
#include <signal.h>
#include <unistd.h>
#include <time.h>
#include <getopt.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <gpiod.h>
#include <sched.h>
#include <pthread.h>
#include <sys/mman.h>

/* Global redefines */
#define STD_FALSE   ((uint8_t)0U)
#define STD_TRUE    ((uint8_t)1U)

/* PINs used for toggle */
#define SOFT_PIN 17
#define HARD_PIN 18

/* Basic frequency for pigpio*/
#define BASIC_FREQUENCY_1HZ ((uint32_t)1000000UL)
/* The number of edges to save to file for synchronization*/
#define EDGES_COUNT         ((uint8_t)4UL)
#define PATH_MAX_LEN        ((uint16_t)512U)

typedef struct led_options {
    uint32_t u32_period_us;
    uint32_t u32_semi_period_us;
    uint32_t u32_freq;
    uint32_t u32_duration_s;
    bool b_relative_sleep;
} led_options_t;

/* Jitter statistics collected during the toggle loop */
typedef struct jitter_stats {
    int64_t min_jitter_ns;
    int64_t max_jitter_ns;
    int64_t sum_jitter_ns;
    uint64_t sum_sq_jitter_ns;  /* For stdev calculation */
    uint32_t count;
} jitter_stats_t;

typedef struct edges_timestamp {
    double start_timestamp[EDGES_COUNT];
    double end_timestamp[EDGES_COUNT];
    uint32_t start_edge_count;
    uint32_t total_edge_count;
    uint8_t start_state[EDGES_COUNT];
    uint8_t end_state[EDGES_COUNT];
} edges_timestamp_t;

static struct option long_options[] = {
    {"nominal-period-us",   required_argument, NULL, 'p'},
    {"duration-s",          required_argument, NULL, 'd'},
    {"output",              required_argument, NULL, 'o'},
    {"relative-toggle-time",no_argument, NULL, 'r'},
    {"help",                no_argument, NULL, 'h'},
    {0, 0, 0, 0} /* Terminal element */
};

typedef struct timespec timespec_t;
typedef void (*fptr_sleep)(uint32_t, timespec_t *);

/* Global flag to control the loop */
volatile sig_atomic_t keepRunning = 1;

/* Register signal handler function whe SIGINT, SIGTERM is received */
void signalHandler(int signum) {
    /* Using write is "async-signal-safe" */
    const char msg[] = "\n--- Signal Handler Caught SIGTERM ---\n";
    write(STDOUT_FILENO, msg, sizeof(msg)-1);

    keepRunning = 0;
}

/* Robust PWM Sysfs writer helper */
bool pwm_write_sysfs(const char *path, const char *value) {
    int fd = open(path, O_WRONLY);
    bool write_status = true;

    if (fd < 0) {
        syslog(LOG_ERR, "PWM: Failed to open %s: %m", path);
        write_status = false;
    } else {
        size_t len = strlen(value);
        ssize_t written = write(fd, value, len);

        /* Close file */
        close(fd);
        
        /* Compare amount written to amount requested to write */
        if (written != (ssize_t)len) {
            syslog(LOG_ERR, "PWM: Failed to write '%s' to %s: %m", value, path);
            write_status = false;
        }
    }
    return write_status;
}

/* Initialize hardware PWM using a safe sequence to prevent glitches and -EINVAL errors */
bool pwm_init(uint32_t period_ns, uint32_t duty_ns) {
    struct stat st;
    bool init_status = true;

    /* Export pwm0 if not already exported */
    if (stat("/sys/class/pwm/pwmchip0/pwm0", &st) != 0) {
        int fd = open("/sys/class/pwm/pwmchip0/export", O_WRONLY);
        if (fd >= 0) {
            write(fd, "0\n", 2);
            close(fd);
            usleep(200000); // Wait for udev to create nodes
        }
    }

    /* Check status of the file after exporting */
    if (stat("/sys/class/pwm/pwmchip0/pwm0", &st) != 0) {
        syslog(LOG_ERR, "PWM: Failed to export pwm0");
        init_status = false;
    } else {
        /* Disable PWM */
        pwm_write_sysfs("/sys/class/pwm/pwmchip0/pwm0/enable", "0\n");

        /* Set duty cycle to 0 first (prevents EINVAL when period changes) */
        pwm_write_sysfs("/sys/class/pwm/pwmchip0/pwm0/duty_cycle", "0\n");

        /* Set period */
        char buf[64];
        snprintf(buf, sizeof(buf), "%u\n", period_ns);
        if (!pwm_write_sysfs("/sys/class/pwm/pwmchip0/pwm0/period", buf)) {
            init_status = false;
        } else {
            /* Set target duty cycle */
            snprintf(buf, sizeof(buf), "%u\n", duty_ns);
            if (!pwm_write_sysfs("/sys/class/pwm/pwmchip0/pwm0/duty_cycle", buf)) {
                init_status = false;
            } else {
                /* Enable PWM */
                if (!pwm_write_sysfs("/sys/class/pwm/pwmchip0/pwm0/enable", "1\n")) {
                    init_status = false;
                } else {
                    syslog(LOG_INFO, "PWM: Initialized with period=%u ns, duty=%u ns", period_ns, duty_ns);
                }
            }
        }
    }

    return init_status;
}

/* Disable PWM and reset duty cycle to 0 */
void pwm_disable(void) {
    pwm_write_sysfs("/sys/class/pwm/pwmchip0/pwm0/enable", "0\n");
    pwm_write_sysfs("/sys/class/pwm/pwmchip0/pwm0/duty_cycle", "0\n");
    syslog(LOG_INFO, "PWM: Disabled");
}

/* Helper function to get current time in seconds */
double get_time_s(void) {
    timespec_t ts;

    /* CLOCK_MONOTONIC is the elapsed time since system boot */
    clock_gettime(CLOCK_MONOTONIC, &ts);

    return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

/* Relative time measurement to the next toggle */
void relative_sleep(uint32_t delay_us, timespec_t *time) {
    (void)time;
    usleep(delay_us);
}

/* Absolute time measurement to the next toggle */
void absolute_sleep(uint32_t delay_us, timespec_t *next_wakeup) {
    /* Calculate exactly when the next rising edge MUST happen */
    next_wakeup->tv_nsec += delay_us * 1000UL;
    while (next_wakeup->tv_nsec >= 1000000000L) {
        next_wakeup->tv_sec++;
        next_wakeup->tv_nsec -= 1000000000L;
    }

    /* Sleep time */
    clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, next_wakeup, NULL);
}

void save_edge(edges_timestamp_t *et, double timestamp, uint8_t edge_state) {
    /* Save to start edge */
    if (et->start_edge_count < EDGES_COUNT) {
        et->start_timestamp[et->start_edge_count] = timestamp;
        et->start_state[et->start_edge_count] = edge_state;
        /* Increase the start edge count */
        et->start_edge_count++;
    }

    /* Otherwise to end edge */
    et->end_timestamp[et->total_edge_count % EDGES_COUNT] = timestamp;
    et->end_state[et->total_edge_count % EDGES_COUNT] = edge_state;
    et->total_edge_count++;
}

/* Call this ONLY when the loop is completely done */
void finalize_and_save_logs(edges_timestamp_t *et, char *output_path) {
    FILE *sync_file = fopen(output_path, "w");

    /* In case opening a file failed */
    if (!sync_file) {
        fprintf(stderr, "File couldn't be open: %s.\n", output_path);
        syslog(LOG_INFO, "File couldn't be open: %s.\n", output_path);
        return;
    }

    fprintf(sync_file, "Time,Channel 0,Edge number\n");
    for (uint32_t i = 0; i < et->start_edge_count; i++) {
        fprintf(sync_file, "%.9f,%u,%u\n", et->start_timestamp[i], et->start_state[i], i);
    }
    
    /* If we haven't even filled the buffer once, wrap around gracefully */
    uint32_t count_to_print = (et->total_edge_count < EDGES_COUNT) ? et->total_edge_count : EDGES_COUNT;
    
    for (uint32_t i = 0; i < count_to_print; i++) {
        /* Chronological calculation: work backwards from the final edge count */
        uint32_t edge_nr = et->total_edge_count - count_to_print + i;
        uint32_t index = edge_nr % EDGES_COUNT;
        fprintf(sync_file, "%.9f,%u,%u\n", et->end_timestamp[index], et->end_state[index], edge_nr);
    }

    fclose(sync_file);
}

/* Helper function to check if a directory exists */
int is_directory_valid(const char *path) {
    int exit_code = EXIT_SUCCESS;
    struct stat statbuf;

    /* Check if path exists */
    if (stat(path, &statbuf) != 0) {
        /* Path does not exist or can't be accessed */
        exit_code = EXIT_FAILURE;
    }
    
    /* Check if the path is a directory (and not a regular file) */
    if (S_ISDIR(statbuf.st_mode) != STD_TRUE) {
        exit_code = EXIT_FAILURE;
    }

    return exit_code;
}

/* Requirement to run */
void print_usage(const char *prog_name) {
    fprintf(stderr, "Usage: %s --nominal-period-us <us> --duration-s <sec> --output <path>\n", prog_name);
    fprintf(stderr, "All three arguments are strictly required.\n");
    syslog(LOG_ERR, "Usage: %s --nominal-period-us <us> --duration-s <sec> --output <path>\n", prog_name);
    syslog(LOG_ERR, "All three arguments are strictly required.\n");
}

/* Handle passed arguments to the file */
int arg_parse(int argc, char **argv, led_options_t *led_param, char *output_path) {
    int exit_code = EXIT_SUCCESS;
    int32_t arg_nr = 0;
    int opt;
    int option_index = 0;
    char *tmp_path = NULL;
    char *endptr = NULL;
    
    /* Extract arguments */
    if ((argv != NULL) && (led_param != NULL) && (output_path != NULL)) {
        /* Loop through the arguments */
        while (((opt = getopt_long(argc, argv, "rp:d:o:h", long_options, &option_index)) != -1) && (exit_code != EXIT_FAILURE)) {
            switch (opt) {
                case 'p':
                    arg_nr = strtol(optarg, &endptr, 10);
                    if (*endptr != '\0' || arg_nr <= 0) {
                        fprintf(stderr, "Error: Period must be a positive integer: %s\n", optarg);
                        print_usage(argv[0]);
                        exit_code = EXIT_FAILURE;
                    } else {
                        led_param->u32_period_us = arg_nr;
                    }
                    break;

                case 'd':
                    arg_nr = strtol(optarg, &endptr, 10);
                    if (*endptr != '\0' || arg_nr <= 0) {
                        fprintf(stderr, "Error: Duration must be a positive integer: %s\n", optarg);
                        print_usage(argv[0]);
                        exit_code = EXIT_FAILURE;
                    } else {
                        led_param->u32_duration_s = arg_nr;
                    }
                    break;

                case 'o':
                    tmp_path = optarg;
                    /* Validate if the directory actually exists */
                    if (is_directory_valid(tmp_path) != EXIT_SUCCESS) {
                        fprintf(stderr, "Error: Output directory '%s' does not exist or is not a valid directory.\n", tmp_path);
                        print_usage(argv[0]);
                        exit_code = EXIT_FAILURE;
                    } else {
                        /* Create output full path with file */
                        int written = snprintf(output_path, PATH_MAX_LEN, "%s/led_toggle_edges.csv", tmp_path);
                        if ((written < 0) || ((size_t)written >= PATH_MAX_LEN)) {
                            fprintf(stderr, "Error: Resulting output file path exceeds safe buffer allocations.\n");
                            exit_code = EXIT_FAILURE;
                        }
                    }
                    break;
                
                case 'r':
                    fprintf(stdout, "Relative toggle time is selected.\n");
                    syslog(LOG_INFO, "Relative toggle time is selected.\n");
                    led_param->b_relative_sleep = true;
                    break;

                case 'h':
                default:
                    print_usage(argv[0]);
                    break;
            }
        }

        /* Make sure that mandatory parameters are present */
        if ((led_param->u32_duration_s == 0) || (led_param->u32_period_us == 0) || (tmp_path == NULL)) {
            fprintf(stderr, "Error: Missing required arguments.\n");
            print_usage(argv[0]);
            exit_code = EXIT_FAILURE;
        }
    } else {
        fprintf(stderr, "Bad null pointer parameters passed to function arg_parse().\n");
    }

    return exit_code;
}

int isolation_priority_cfg(void) {
    int exit_code = EXIT_SUCCESS;

    /* Lock all current and future pages in RAM — mandatory for RT */
    if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0) {
        syslog(LOG_WARNING, "mlockall failed: %m — page faults may cause jitter");
        exit_code = EXIT_FAILURE;
    }

    /* Pin this thread to an isolated CPU core (core 3) */
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(3, &cpuset);
    if (sched_setaffinity(0, sizeof(cpuset), &cpuset) != 0) {
        syslog(LOG_WARNING, "Failed to set CPU affinity to core 3: %m");
        exit_code = EXIT_FAILURE;
    } else {
        syslog(LOG_INFO, "Pinned to CPU core 3 for RT isolation.");
    }

    /* Set real-time scheduling from within the process */
    struct sched_param sp = { .sched_priority = 99 };
    if (sched_setscheduler(0, SCHED_FIFO, &sp) != 0) {
        syslog(LOG_WARNING, "Failed to set SCHED_FIFO: %m");
        exit_code = EXIT_FAILURE;
    }

    return exit_code;
}

int main(int argc, char **argv) {
    int exit_code = EXIT_SUCCESS;

    /* Core isolation and priority set */
    if (isolation_priority_cfg() != EXIT_SUCCESS) {
        exit_code = EXIT_FAILURE;
    } else {
        struct sigaction action = { .sa_handler = signalHandler };

        /* Toggle specific needs */
        bool gpiod_initialized = false;
        bool pwm_initialized = false;
        led_options_t led_param = {0};
        char output_path[PATH_MAX_LEN] = {0};
        /* Synchronization tracking arrays with edges timestamp */
        edges_timestamp_t et = {0};
        jitter_stats_t jstats = { .min_jitter_ns = INT64_MAX, .max_jitter_ns = INT64_MIN, .sum_jitter_ns = 0, .sum_sq_jitter_ns = 0, .count = 0 };

        /* Time wakeup */
        timespec_t next_wakeup;
        fptr_sleep time_sleep_ptr = NULL;

        /* Time related variables */
        double start_time = get_time_s();
        double current_time = start_time;
        double end_time = 0.0;

        /* gpiod handles */
        struct gpiod_chip *chip = NULL;
        struct gpiod_line_settings *output_settings = NULL;
        struct gpiod_line_settings *input_settings = NULL;
        struct gpiod_line_config *output_line_cfg = NULL;
        struct gpiod_line_config *input_line_cfg = NULL;
        struct gpiod_request_config *req_cfg = NULL;
        struct gpiod_line_request *request = NULL;

        /* Open a connection to the system logger */
        openlog("LedToggleService", LOG_PID | LOG_CONS, LOG_USER);
        syslog(LOG_INFO, "GPIO Toggle Service (using libgpiod v2).");

        /* Catch the SIGTERM signal sent by 'systemctl stop' */
        sigaction(SIGTERM, &action, NULL);
        sigaction(SIGINT, &action, NULL);

        /* Parse arguments */
        exit_code = arg_parse(argc, argv, &led_param, output_path);

        /* Initialize GPIO via libgpiod v2 */
        if (exit_code == EXIT_SUCCESS) {
            /* Open a chip by path*/
            chip = gpiod_chip_open("/dev/gpiochip0");
            if (!chip) {
                syslog(LOG_ERR, "GPIO: Failed to open /dev/gpiochip0: %m");
                exit_code = EXIT_FAILURE;
            } else {
                /* Create a new line settings object */
                output_settings = gpiod_line_settings_new();
                if (!output_settings) {
                    syslog(LOG_ERR, "GPIO: Failed to allocate line settings");
                    exit_code = EXIT_FAILURE;
                } else {
                    /* Set pin direction and output value */
                    gpiod_line_settings_set_direction(output_settings, GPIOD_LINE_DIRECTION_OUTPUT);
                    gpiod_line_settings_set_output_value(output_settings, GPIOD_LINE_VALUE_INACTIVE);

                    /* Create a new line config object */
                    output_line_cfg = gpiod_line_config_new();
                    if (!output_line_cfg) {
                        syslog(LOG_ERR, "GPIO: Failed to allocate line config");
                        exit_code = EXIT_FAILURE;
                    } else {
                        unsigned int offset = SOFT_PIN;

                        /* Based on line settings of the pin for the direction and output,
                        * of the line configuration; apply it to the array of offsets,
                        * in this case SOFT_PIN
                        */
                        if (gpiod_line_config_add_line_settings(output_line_cfg, &offset, 1, output_settings) < 0) {
                            syslog(LOG_ERR, "GPIO: Failed to add line settings for pin %u: %m", offset);
                            exit_code = EXIT_FAILURE;
                        } else {
                            /* Create a new request config object */
                            req_cfg = gpiod_request_config_new();
                            if (!req_cfg) {
                                syslog(LOG_ERR, "GPIO: Failed to allocate request config");
                                exit_code = EXIT_FAILURE;
                            } else {
                                /* Set the consumer name of the request */
                                gpiod_request_config_set_consumer(req_cfg, "led-toggle");
                                /* Request a set of lines for exclusive usage */
                                request = gpiod_chip_request_lines(chip, req_cfg, output_line_cfg);
                                if (!request) {
                                    syslog(LOG_ERR, "GPIO: Failed to request GPIO lines: %m");
                                    exit_code = EXIT_FAILURE;
                                } else {
                                    gpiod_initialized = true;
                                }
                            }
                        }
                    }
                }
            }
        }

        /* Main logic */
        if (gpiod_initialized == true)
        {
            /* Calculate end time and log it. */
            end_time = start_time + (double)led_param.u32_duration_s;

            syslog(LOG_INFO, "Start time and end duration time is: %.9f and %.9f.", start_time, end_time);

            /* Calculate periods */
            led_param.u32_semi_period_us = (uint32_t)(led_param.u32_period_us / 2U);
            led_param.u32_freq = BASIC_FREQUENCY_1HZ / led_param.u32_period_us;
            
            /* Duty cycle for sysfs (nanoseconds) */
            uint32_t period_ns = 1000000000U / led_param.u32_freq;
            uint32_t duty_ns = period_ns / 2U;

            /* Summary running information */
            if (led_param.b_relative_sleep == true) {
                syslog(LOG_INFO, "Semi-period: %d\nFrequency: %d\nDuration: %d\nPath:%s\n Toggle time:%s",
                    led_param.u32_semi_period_us, led_param.u32_freq, led_param.u32_duration_s, output_path, "relative");
                time_sleep_ptr = relative_sleep;
            } else {
                syslog(LOG_INFO, "Semi-period: %d\nFrequency: %d\nDuration: %d\nPath:%s\n Toggle time:%s",
                    led_param.u32_semi_period_us, led_param.u32_freq, led_param.u32_duration_s, output_path, "absolute");
                time_sleep_ptr = absolute_sleep;
            }

            /* Hardware PWM (GPIO 18) via sysfs helper */
            if (!pwm_init(period_ns, duty_ns)) {
                syslog(LOG_ERR, "PWM: Failed to initialize PWM.");
                exit_code = EXIT_FAILURE;
            } else {
                pwm_initialized = true;
            }
        }

        if (gpiod_initialized && pwm_initialized) {
            /* Initialize the baseline timestamp exactly ONCE before the loop */
            clock_gettime(CLOCK_MONOTONIC, &next_wakeup);

            /* Main toggle loop */
            while ((keepRunning) && (current_time < end_time)) {
                struct timespec ts_before, ts_after;
                
                save_edge(&et, get_time_s(), 1);
                gpiod_line_request_set_value(request, SOFT_PIN, GPIOD_LINE_VALUE_ACTIVE);
                
                clock_gettime(CLOCK_MONOTONIC, &ts_before);
                time_sleep_ptr(led_param.u32_semi_period_us, &next_wakeup);
                clock_gettime(CLOCK_MONOTONIC, &ts_after);

                int64_t actual_ns = (int64_t)(ts_after.tv_sec - ts_before.tv_sec) * 1000000000LL + (ts_after.tv_nsec - ts_before.tv_nsec);
                int64_t expected_ns = (int64_t)led_param.u32_semi_period_us * 1000LL;
                int64_t jitter_ns = actual_ns - expected_ns;
                
                if (jitter_ns < jstats.min_jitter_ns) jstats.min_jitter_ns = jitter_ns;
                if (jitter_ns > jstats.max_jitter_ns) jstats.max_jitter_ns = jitter_ns;
                jstats.sum_jitter_ns += jitter_ns;
                jstats.sum_sq_jitter_ns += (uint64_t)(jitter_ns * jitter_ns);
                jstats.count++;

                save_edge(&et, get_time_s(), 0);
                gpiod_line_request_set_value(request, SOFT_PIN, GPIOD_LINE_VALUE_INACTIVE);
                
                clock_gettime(CLOCK_MONOTONIC, &ts_before);
                time_sleep_ptr(led_param.u32_semi_period_us, &next_wakeup);
                clock_gettime(CLOCK_MONOTONIC, &ts_after);

                actual_ns = (int64_t)(ts_after.tv_sec - ts_before.tv_sec) * 1000000000LL + (ts_after.tv_nsec - ts_before.tv_nsec);
                jitter_ns = actual_ns - expected_ns;
                
                if (jitter_ns < jstats.min_jitter_ns) jstats.min_jitter_ns = jitter_ns;
                if (jitter_ns > jstats.max_jitter_ns) jstats.max_jitter_ns = jitter_ns;
                jstats.sum_jitter_ns += jitter_ns;
                jstats.sum_sq_jitter_ns += (uint64_t)(jitter_ns * jitter_ns);
                jstats.count++;

                /* Update time */
                current_time = get_time_s();
            }

            /* Reconfigure pin to high-impedance input on exit */
            input_settings = gpiod_line_settings_new();
            input_line_cfg = gpiod_line_config_new();
            if (input_settings && input_line_cfg) {
                gpiod_line_settings_set_direction(input_settings, GPIOD_LINE_DIRECTION_INPUT);
                unsigned int offset = SOFT_PIN;
                if (gpiod_line_config_add_line_settings(input_line_cfg, &offset, 1, input_settings) == 0) {
                    gpiod_line_request_reconfigure_lines(request, input_line_cfg);
                    syslog(LOG_INFO, "GPIO: Reconfigured pin %u to input (high-impedance) on exit.", SOFT_PIN);
                }
            }

            /* Free gpiod objects */
            if (input_settings) gpiod_line_settings_free(input_settings);
            if (input_line_cfg) gpiod_line_config_free(input_line_cfg);

            /* Turn off PWM */
            pwm_disable();

            /* Save edges timestamp */
            finalize_and_save_logs(&et, output_path);
            
            if (jstats.count > 0) {
                double avg_jitter = (double)jstats.sum_jitter_ns / jstats.count;
                syslog(LOG_INFO, "Jitter Stats: count=%u, min=%ld ns, max=%ld ns, avg=%.2f ns",
                    jstats.count, jstats.min_jitter_ns, jstats.max_jitter_ns, avg_jitter);
            }
        
            /* Notify about shutting down the service */
            syslog(LOG_INFO, "Service shutting down.");
        }

        /* Cleanup libgpiod resources */
        if (request) gpiod_line_request_release(request);
        if (req_cfg) gpiod_request_config_free(req_cfg);
        if (output_line_cfg) gpiod_line_config_free(output_line_cfg);
        if (output_settings) gpiod_line_settings_free(output_settings);
        if (chip) gpiod_chip_close(chip);

        /* Close system logger */
        closelog();
    }

    return exit_code;
}
