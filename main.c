#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <netdb.h>

#include <ws2811.h>

// set to your data pin
#define GPIO_PIN 12

#define DMA 10

// set to your # of leds
#define LED_COUNT 93 + 96

#define PORT 7805
#define BUFSIZE 32768

#define CMD_CLEAR 0
#define CMD_SET 1
#define CMD_FILL 2
#define CMD_SHOW 3

int led_count = LED_COUNT;

ws2811_t ledstring = {
    .freq = WS2811_TARGET_FREQ,
    .dmanum = DMA,
    .channel = {
        [0] =
        {
            .gpionum = GPIO_PIN,
            .invert = 0,
            .count = LED_COUNT,
            .strip_type = WS2811_STRIP_RGB,
            .brightness = 64,
        },
        [1] = {
            .gpionum = 0,
            .invert = 0,
            .count = 0,
            .brightness = 0,
        }
    }
};

ws2811_led_t *strip;

static uint8_t running = 1;

void render() {
    for (int i = 0; i < led_count; i++) {
        ledstring.channel[0].leds[i] = strip[i];
    }
}

void fill(int color) {
    for (int i = 0; i < led_count; i++) {
        strip[i] = color;
    }
}

void clear() {
    for (int i = 0; i < led_count; i++) {
        strip[i] = 0;
    }
}

int encode_rgb(uint8_t r, uint8_t g, uint8_t b) {
    return (g << 16) + (r << 8) + b;
}

static void ctrl_c_handler(int signum) {
	(void) signum;
    running = 0;
}

static void setup_handlers(void) {
    struct sigaction sa = {
        .sa_handler = ctrl_c_handler,
    };

    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);
}

int main() {
    char buffer[BUFSIZE];
    char protoname[] = "tcp";
    struct protoent *protoent;
    int enable = 1;
    int server_sockfd, client_sockfd;
    socklen_t client_len;
//    ssize_t nbytes_read;
    struct sockaddr_in client_address, server_address;
    unsigned short server_port = PORT;

    protoent = getprotobyname(protoname);
    if (protoent == NULL) {
        perror("getprotobyname");
        exit(EXIT_FAILURE);
    }

    server_sockfd = socket(
            AF_INET,
            SOCK_STREAM,
            protoent->p_proto
    );
    if (server_sockfd == -1) {
        perror("socket");
        exit(EXIT_FAILURE);
    }

    if (setsockopt(server_sockfd, SOL_SOCKET, SO_REUSEADDR, &enable, sizeof(enable)) < 0) {
        perror("setsockopt(SO_REUSEADDR) failed");
        exit(EXIT_FAILURE);
    }

    server_address.sin_family = AF_INET;
    server_address.sin_addr.s_addr = htonl(INADDR_ANY);
    server_address.sin_port = htons(server_port);
    if (bind(
            server_sockfd,
            (struct sockaddr*)&server_address,
            sizeof(server_address)
    ) == -1) {
        perror("bind");
        exit(EXIT_FAILURE);
    }

    if (listen(server_sockfd, 5) == -1) {
        perror("listen");
        exit(EXIT_FAILURE);
    }
    fprintf(stderr, "listening on port %d\n", server_port);

    // Setup strip
    ws2811_return_t ret;

    strip = malloc(sizeof(ws2811_led_t) * led_count);

    setup_handlers();

    if ((ret = ws2811_init(&ledstring)) != WS2811_SUCCESS) {
        fprintf(stderr, "ws2811_init failed: %s\n", ws2811_get_return_t_str(ret));
        return ret;
    }

    // Loop
    while (running) {
        client_len = sizeof(client_address);
        client_sockfd = accept(
                server_sockfd,
                (struct sockaddr*)&client_address,
                &client_len
        );
        ssize_t size;
        while ((size = read(client_sockfd, buffer, BUFSIZE)) > 0) {
            int offset = 0;
            while (offset < size) {
                uint16_t num_cmds = (buffer[offset + 1] << 8) | buffer[offset];
                offset += 2;
                for (int i = 0; i < num_cmds; i++) {
                    uint8_t cmd = buffer[offset++];
                    if (cmd == CMD_CLEAR) {
                        clear();
                    } else if (cmd == CMD_SET) {
                        uint8_t ind = buffer[offset++];
                        uint8_t r = buffer[offset++];
                        uint8_t g = buffer[offset++];
                        uint8_t b = buffer[offset++];
                        if (ind > (led_count - 1)) {
                            continue;  // out of bounds
                        }
                        strip[ind] = encode_rgb(r, g, b);
                    } else if (cmd == CMD_FILL) {
                        uint8_t r = buffer[offset++];
                        uint8_t g = buffer[offset++];
                        uint8_t b = buffer[offset++];
                        fill(encode_rgb(r, g, b));
                    } else if (cmd == CMD_SHOW) {
                        render();
                        if ((ret = ws2811_render(&ledstring)) != WS2811_SUCCESS) {
                            fprintf(stderr, "ws2811_render failed: %s\n", ws2811_get_return_t_str(ret));
                            break;
                        }
                    }
                }
            }
        }
        close(client_sockfd);
    }

    // Finalize
    ws2811_fini(&ledstring);

    return ret;
}

