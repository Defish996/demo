#pragma once
#include <string>
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <arpa/inet.h>

using json = nlohmann::json;

int main()
{
    const char* host = "example.com";
    const int port = 8080;

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    i(sock < 0) {
        perror("Socket creation failed");
        return 1;
    }

    sockaddr_in addr{};

}