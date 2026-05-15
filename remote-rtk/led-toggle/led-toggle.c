#include <pigpio.h>
#include <stdio.h>
#include <syslog.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>

#define STD_OK      ((uint8_t)0U)
#define STD_NOK     ((uint8_t)1U)
#define STD_FALSE   ((uint8_t)0U)
#define STD_TRUE    ((uint8_t)1U)

#define SOFT_PIN 17
#define HARD_PIN 18

#define BASIC_FREQUENCY_1HZ ((uint32_t)1000000UL)

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

int main(int argc, char **argv) {
    int exit_code = STD_OK;
    int pigpio_initialized = STD_FALSE;
    struct sigaction action = { .sa_handler = signalHandler };
    uint32_t lu32_frequency = 0UL;
    uint32_t lu32_duty = 0UL;
    uint32_t lu32_period = 0UL;
    uint32_t lu32_semi_period = 0UL;

    /* Open a connection to the system logger */
    openlog("LedToggleService", LOG_PID | LOG_CONS, LOG_USER);
    syslog(LOG_INFO, "GPIO Toggle Service started.");

    /* Catch the SIGTERM signal sent by 'systemctl stop' */
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);

    /* Extract arguments */
    if (argc != 2)
    {
        syslog(LOG_ERR, "Bad arguments. Expected 1 (period in us), got %d.", argc - 1);
        exit_code = STD_NOK;
    }
    else
    {
        /* Extract the period */
        lu32_period = (uint32_t)atoi(argv[1]);

        /* Validate the extracted period to prevent issues with atoi returning 0 on error */
        if (lu32_period == 0) {
            syslog(LOG_ERR, "Invalid or zero period provided. Argument was: '%s'", argv[1]);
            exit_code = STD_NOK;
        }
    }

    /* Initialize pigpio */
    if (exit_code == STD_OK) {
        /* This prevents pigpio from handling signals, which we do ourselves */
        gpioCfgSetInternals(gpioCfgGetInternals() | PI_CFG_NOSIGHANDLER);

        if (gpioInitialise() < 0)
        {
            syslog(LOG_ERR, "Failed to initialize pigpio!");
            exit_code = STD_NOK;
        }
        else
        {
            pigpio_initialized = STD_TRUE;
        }
    }

    /* Main logic */
    if (pigpio_initialized == STD_TRUE)
    {
        /* Calculate periods */
        lu32_semi_period = (uint32_t)(lu32_period / 2U);
        lu32_frequency = BASIC_FREQUENCY_1HZ /lu32_period;
        lu32_duty = PI_HW_PWM_RANGE / 2U;

        syslog(LOG_INFO, "Semi-period: %d\nFrequency: %d\nDuty cycle: %d\n", lu32_semi_period, lu32_frequency, lu32_duty);

        /* Hardware PWM (GPIO 18) - 1Hz, 50% duty cycle */
        gpioHardwarePWM(HARD_PIN, lu32_frequency, lu32_duty); 
        syslog(LOG_INFO, "Hardware PWM initialized on GPIO 18.");
    
        gpioSetMode(SOFT_PIN, PI_OUTPUT);
    
        while (keepRunning) {
            gpioWrite(SOFT_PIN, 1);
            syslog(LOG_DEBUG, "Soft Pin 17: HIGH");
            usleep(lu32_semi_period);
    
            gpioWrite(SOFT_PIN, 0);
            syslog(LOG_DEBUG, "Soft Pin 17: LOW");
            usleep(lu32_semi_period);
        }
    
        /* Notify about shuting down the service */
        syslog(LOG_INFO, "Service shutting down.");
        
        /* leave pin state to high */
        gpioWrite(SOFT_PIN, 1);
    
        /* Turn off PWM */
        stop_hardware_pwm(HARD_PIN);
    
        /* Close the pigpio and logging */
        gpioTerminate();
    }

    /* Close system logger */
    closelog();

    return exit_code;
}
