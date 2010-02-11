#ifndef __IO_BASE_H__
#define __IO_BASE_H__

extern int sendfd(int dst_fd, int fd);
extern int recvfd(int src_fd);

#ifdef WIN32
extern void winsock_init (void);
extern int winsock_write (int sockfd, void *buffer, int len);
extern int winsock_read (int sockfd, void *buffer, int len);
#endif

#endif