#include <pigpio.h>
#include <stdio.h>
#include <syslog.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>

#define SOFT_PIN 17
#define HARD_PIN 18

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

int main() {
    struct sigaction action;

    memset(&action, 0, sizeof(struct sigaction));
    action.sa_handler = signalHandler;

    /* This prevents the "Unhandled signal" message you saw */
    gpioCfgSetInternals(gpioCfgGetInternals() | PI_CFG_NOSIGHANDLER);

    /* Catch the SIGTERM signal sent by 'systemctl stop' */
    sigaction(SIGTERM, &action, NULL);
    sigaction(SIGINT, &action, NULL);

    /* Open a connection to the system logger */
    openlog("LedToggleService", LOG_PID | LOG_CONS, LOG_USER);
    syslog(LOG_INFO, "GPIO Toggle Service started.");

    if (gpioInitialise() < 0) {
        syslog(LOG_ERR, "Failed to initialize pigpio!");
        return 1;
    }

    /* Hardware PWM (GPIO 18) - 1Hz, 50% duty cycle */
    gpioHardwarePWM(HARD_PIN, 1, 500000); 
    syslog(LOG_INFO, "Hardware PWM initialized on GPIO 18.");

    gpioSetMode(SOFT_PIN, PI_OUTPUT);

    while (keepRunning) {
        gpioWrite(SOFT_PIN, 1);
        syslog(LOG_DEBUG, "Soft Pin 17: HIGH");
        time_sleep(0.5);

        gpioWrite(SOFT_PIN, 0);
        syslog(LOG_DEBUG, "Soft Pin 17: LOW");
        time_sleep(0.5);
    }

    /* leave pin state to high */
    gpioWrite(SOFT_PIN, 1);

    /* Notify about shuting down the service */
    syslog(LOG_INFO, "Service shutting down.");

    /* Turn off PWM */
    stop_hardware_pwm(HARD_PIN);

    /* Close the pigpio and logging */
    gpioTerminate();
    closelog();

    return 0;
}
