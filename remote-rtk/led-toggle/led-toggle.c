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
#include <pigpio.h>

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
    uint32_t u32_duty;
    uint32_t u32_duration_s;
} led_options_t;

typedef struct edges_timestamp {
    double start_edges[EDGES_COUNT];
    double end_edges[EDGES_COUNT];
    uint32_t start_edge_count;
    uint32_t total_edge_count;
} edges_timestamp_t;

static struct option long_options[] = {
    {"nominal-period-us",   required_argument, NULL, 'p'},
    {"duration-s",          required_argument, NULL, 'd'},
    {"output",              required_argument, NULL, 'o'},
    {"help",                no_argument, NULL, 'h'},
    {0, 0, 0, 0} /* Terminal element */
};

/* Global flag to control the loop */
volatile sig_atomic_t keepRunning = 1;

/* Register signal handler function whe SIGINT, SIGTERM is received */
void signalHandler(int signum) {
    /* Using write is "async-signal-safe" */
    const char msg[] = "\n--- Signal Handler Caught SIGTERM ---\n";
    write(STDOUT_FILENO, msg, sizeof(msg)-1);

    keepRunning = 0;
}

/* Stoping hardware PWM */
void stop_hardware_pwm(int pin) {
    /* Set frequency and duty cycle to 0 */
    gpioHardwarePWM(pin, 0, 0); 
    
    /* Small delay to allow the hardware buffer to clear */
    time_sleep(0.01); 
    
    /* Force the pin back to a standard Output mode */
    gpioSetMode(pin, PI_OUTPUT);
    
    /* Explicitly write high to be safe */
    gpioWrite(pin, 1);
    
    syslog(LOG_INFO, "Hardware PWM on pin %d fully disabled.", pin);
}

/* Helper function to get current time in seconds */
double get_time_s(void) {
    struct timespec ts;

    /* CLOCK_MONOTONIC is the elapsed time since system boot */
    clock_gettime(CLOCK_MONOTONIC, &ts);

    return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

void save_edge(edges_timestamp_t *et, double timestamp) {
    /* Save to start edge */
    if (et->start_edge_count < EDGES_COUNT) {
        et->start_edges[et->start_edge_count] = timestamp;
        /* Increase the start edge count */
        et->start_edge_count++;
    }

    /* Otherwise to end edge */
    et->end_edges[et->total_edge_count % EDGES_COUNT] = timestamp;
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

    fprintf(sync_file, "[START_SIGNATURE]\n");
    for (uint32_t i = 0; i < et->start_edge_count; i++) {
        fprintf(sync_file, "edge_%d=%.9f\n", i, et->start_edges[i]);
    }

    fprintf(sync_file, "\n[END_SIGNATURE]\n");
    
    /* If we haven't even filled the buffer once, wrap around gracefully */
    uint32_t count_to_print = (et->total_edge_count < EDGES_COUNT) ? et->total_edge_count : EDGES_COUNT;
    
    for (uint32_t i = 0; i < count_to_print; i++) {
        /* Chronological calculation: work backwards from the final edge count */
        uint32_t index = (et->total_edge_count - count_to_print + i) % EDGES_COUNT;
        fprintf(sync_file, "edge_%d=%.9f\n", i, et->end_edges[index]);
    }

    fclose(sync_file);
}

/* Helper function to check if a directory exists */
int is_directory_valid(const char *path) {
    int exit_code = EXIT_SUCCESS;
    struct stat statbuf;

    /* Check if path exists */
    if ((stat(path, &statbuf) != 0)
            /* Check if the path is a directory (and not a regular file) */
            && (S_ISDIR(statbuf.st_mode) != STD_TRUE)) {
        /* Path does not exist or can't be accessed */
        exit_code = EXIT_FAILURE;
    }

    return exit_code;
}

/* Requirement to run */
void print_usage(const char *prog_name) {
    fprintf(stderr, "Usage: %s --nominal-period-us <us> --duration-s <sec> --output <path>\n", prog_name);
    fprintf(stderr, "All three arguments are strictly required.\n");
    syslog(LOG_INFO, "Usage: %s --nominal-period-us <us> --duration-s <sec> --output <path>\n", prog_name);
    syslog(LOG_INFO, "All three arguments are strictly required.\n");
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
        while (((opt = getopt_long(argc, argv, "p:d:o:h", long_options, &option_index)) != -1) && (exit_code != EXIT_FAILURE)) {
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
                        strncpy(output_path, tmp_path, PATH_MAX_LEN - 1U);
                        strcat(output_path, "/led_toggle_edges.txt");
                    }
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

int main(int argc, char **argv) {
    int exit_code = EXIT_SUCCESS;
    struct sigaction action = { .sa_handler = signalHandler };

    /* Toggle specific needs */
    int pigpio_initialized = STD_FALSE;
    led_options_t led_param = {0};
    char output_path[PATH_MAX_LEN] = {0};
    /* Synchronization tracking arrays with edges timestamp */
    edges_timestamp_t et = {0};

    /* Time related variables */
    double start_time = get_time_s();
    double current_time = start_time;
    double end_time = 0.0;

    /* Open a connection to the system logger */
    openlog("LedToggleService", LOG_PID | LOG_CONS, LOG_USER);
    syslog(LOG_INFO, "GPIO Toggle Service.");

    /* Catch the SIGTERM signal sent by 'systemctl stop' */
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);

    /* Parse arguments */
    exit_code = arg_parse(argc, argv, &led_param, output_path);

    /* Initialize pigpio */
    if (exit_code == EXIT_SUCCESS) {
        /* This prevents pigpio from handling signals, which we do ourselves */
        gpioCfgSetInternals(gpioCfgGetInternals() | PI_CFG_NOSIGHANDLER);

        if (gpioInitialise() < 0)
        {
            syslog(LOG_ERR, "Failed to initialize pigpio!");
            exit_code = EXIT_FAILURE;
        }
        else
        {
            pigpio_initialized = STD_TRUE;
        }
    }

    /* Main logic */
    if (pigpio_initialized == STD_TRUE)
    {
        /* Calculate end time and log it. */
        end_time = start_time + (double)led_param.u32_duration_s;

        syslog(LOG_INFO, "Start time and end duration time is: %.1f and %.1f.", start_time, end_time);

        /* Calculate periods */
        led_param.u32_semi_period_us = (uint32_t)(led_param.u32_period_us / 2U);
        led_param.u32_freq = BASIC_FREQUENCY_1HZ / led_param.u32_period_us;
        led_param.u32_duty = PI_HW_PWM_RANGE - PI_HW_PWM_RANGE / 2U;

        syslog(LOG_INFO, "Semi-period: %d\nFrequency: %d\nDuty cycle: %d\nDuration: %d\nPath:%s",
            led_param.u32_semi_period_us, led_param.u32_freq, led_param.u32_duty, led_param.u32_duration_s, output_path);

        /* Hardware PWM (GPIO 18) - 1Hz, 50% duty cycle */
        gpioHardwarePWM(HARD_PIN, led_param.u32_freq, led_param.u32_duty); 
        syslog(LOG_INFO, "Hardware PWM initialized on GPIO 18.");
    
        gpioSetMode(SOFT_PIN, PI_OUTPUT);
    
        while ((keepRunning) && (current_time < end_time)) {
            save_edge(&et, get_time_s());
            gpioWrite(SOFT_PIN, 1);
            usleep(led_param.u32_semi_period_us);
    
            save_edge(&et, get_time_s());
            gpioWrite(SOFT_PIN, 0);
            usleep(led_param.u32_semi_period_us);

            /* Update time */
            current_time = get_time_s();
        }

        /* Turn off PWM */
        stop_hardware_pwm(HARD_PIN);

        /* leave pin state to high */
        gpioWrite(SOFT_PIN, 1);

        /* Save edges timestamp */
        finalize_and_save_logs(&et, output_path);
    
        /* Notify about shuting down the service */
        syslog(LOG_INFO, "Service shutting down.");
        
        /* Close the pigpio and logging */
        gpioTerminate();
    }

    /* Close system logger */
    closelog();

    return exit_code;
}
