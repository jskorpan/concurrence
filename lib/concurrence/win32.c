#ifdef WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <stdio.h>

void winsock_init (void)
{
    static WSADATA s_wsaData;
    static int s_once = 1;

    if (!s_once)
    {
        return;
    }

    WSAStartup (MAKEWORD(2,0), &s_wsaData);

    s_once = 0;

}

#endif