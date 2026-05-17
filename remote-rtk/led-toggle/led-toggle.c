#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include <syslog.h>
#include <signal.h>
#include <unistd.h>
#include <time.h>
#include <getopt.h>
#include <pigpio.h>

#define STD_FALSE   ((uint8_t)0U)
#define STD_TRUE    ((uint8_t)1U)

#define SOFT_PIN 17
#define HARD_PIN 18

#define BASIC_FREQUENCY_1HZ ((uint32_t)1000000UL)

typedef struct led_options {
    uint32_t u32_period_us;
    uint32_t u32_semi_period_us;
    uint32_t u32_freq;
    uint32_t u32_duty;
    uint32_t u32_duration_s;
} led_options_t;

static struct option long_options[] = {
    {"nominal-period-us",   required_argument, NULL, 'p'},
    {"duration-s",          required_argument, NULL, 'd'},
    {"help",                no_argument, NULL, 'h'},
    {0, 0, 0, 0} /* Terminal element */
};

/* Global flag to control the loop */
volatile sig_atomic_t keepRunning = 1;

void signalHandler(int signum) {
    /* Using write is "async-signal-safe" */
    const char msg[] = "\n--- Signal Handler Caught SIGTERM ---\n";
    write(STDOUT_FILENO, msg, sizeof(msg)-1);

    keepRunning = 0;
}

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

/* Handle passed arguments to the file */
int arg_parse(int argc, char **argv, led_options_t *led_param) {
    int exit_code = EXIT_SUCCESS;
    int32_t arg_nr = 0;
    int opt;
    int option_index = 0;
    
    /* Extract arguments */
    if (argc < 2) {
        fprintf(stderr, "Usage: %s --nominal-period-us <us> --duration-s <sec>\n", argv[0]);
    } else {
        /* Loop through the arguments */
        while (((opt = getopt_long(argc, argv, "p:d:h", long_options, &option_index)) != -1) && (exit_code != EXIT_FAILURE)) {
            switch (opt) {
                case 'p':
                    arg_nr = strtol(optarg, NULL, 10);
                    if (arg_nr <= 0) {
                        fprintf(stderr, "Error: Period must be a positive integer: %s\n", optarg);
                        exit_code = EXIT_FAILURE;
                    } else {
                        led_param->u32_period_us = arg_nr;
                    }
                    break;

                case 'd':
                    arg_nr = strtol(optarg, NULL, 10);
                    if (arg_nr <= 0) {
                        fprintf(stderr, "Error: Duration must be a positive integer: %s\n", optarg);
                        exit_code = EXIT_FAILURE;
                    } else {
                        led_param->u32_duration_s = arg_nr;
                    }
                    break;
                
                case 'h':
                default:
                    fprintf(stderr, "Usage: %s --nominal-period-us <us> --duration-s <sec>\n", argv[0]);
                    break;
            }
        }

        /* Make sure that mandatory parameters are present */
        if ((led_param->u32_duration_s == 0) || (led_param->u32_period_us == 0)) {
            fprintf(stderr, "Both parameters are required.\n");
            fprintf(stderr, "Usage: %s --nominal-period-us <us> --duration-s <sec>\n", argv[0]);
            exit_code = EXIT_FAILURE;
        }
    }

    return exit_code;
}

int main(int argc, char **argv) {
    int exit_code = EXIT_SUCCESS;
    int pigpio_initialized = STD_FALSE;
    struct sigaction action = { .sa_handler = signalHandler };
    led_options_t led_param = {0};
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
    exit_code = arg_parse(argc, argv, &led_param);

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

        syslog(LOG_INFO, "Semi-period: %d\nFrequency: %d\nDuty cycle: %d\nDuration: %d\n",
            led_param.u32_semi_period_us, led_param.u32_freq, led_param.u32_duty, led_param.u32_duration_s);

        /* Hardware PWM (GPIO 18) - 1Hz, 50% duty cycle */
        gpioHardwarePWM(HARD_PIN, led_param.u32_freq, led_param.u32_duty); 
        syslog(LOG_INFO, "Hardware PWM initialized on GPIO 18.");
    
        gpioSetMode(SOFT_PIN, PI_OUTPUT);
    
        while ((keepRunning) && (current_time < end_time)) {
            gpioWrite(SOFT_PIN, 1);
            syslog(LOG_DEBUG, "Soft Pin 17: HIGH");
            usleep(led_param.u32_semi_period_us);
    
            gpioWrite(SOFT_PIN, 0);
            syslog(LOG_DEBUG, "Soft Pin 17: LOW");
            usleep(led_param.u32_semi_period_us);

            /* Update time */
            current_time = get_time_s();
        }
    
        /* Notify about shuting down the service */
        syslog(LOG_INFO, "Service shutting down.");
        
        /* Turn off PWM */
        stop_hardware_pwm(HARD_PIN);

        /* leave pin state to high */
        gpioWrite(SOFT_PIN, 1);
        
        /* Close the pigpio and logging */
        gpioTerminate();
    }

    /* Close system logger */
    closelog();

    return exit_code;
}
