#include "io_base.h"

#ifdef WIN32
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <windows.h>
#include <stdio.h>

int sendfd(int dst_fd, int fd)
{
    fprintf (stdout, "%s: dst=%d, fd=%d\n", __FUNCTION__, dst_fd, fd);
    return -1;
}

int recvfd(int src_fd)
{
    fprintf (stdout, "%s: src=%\n", __FUNCTION__, src_fd);
    return -1;
}

int winsock_write (int sockfd, void *buffer, int len)
{
   int result = send ( (SOCKET) sockfd, buffer, len, 0);
   //fprintf (stderr, "%s:[%08x] %p %08x %08x %08x\n", "write", sockfd, buffer, len, result, WSAGetLastError());
   return result;
}

int winsock_read (int sockfd, void *buffer, int len)
{
    int result = recv ( (SOCKET) sockfd, buffer, len, 0);
    //fprintf (stderr, "%s:[%08x] %p %08x %08x %08x\n", "read ", sockfd, buffer, len, result, WSAGetLastError ());
    return result;
}

#else

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>

#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>

int sendfd(int dst_fd, int fd)
{
	int file_descriptors[1] = { fd };
	char buffer[CMSG_SPACE(sizeof file_descriptors)];
	struct msghdr message = {
	  .msg_control = buffer,
	  .msg_controllen = sizeof buffer,
	};
	struct cmsghdr *cmessage = CMSG_FIRSTHDR(&message);
	cmessage->cmsg_level = SOL_SOCKET;
	cmessage->cmsg_type = SCM_RIGHTS;
	cmessage->cmsg_len = CMSG_LEN(sizeof file_descriptors);
	message.msg_controllen = cmessage->cmsg_len;
	memcpy(CMSG_DATA(cmessage), file_descriptors, sizeof file_descriptors);
	char ping = 23;
	struct iovec ping_vec = {
	  .iov_base = &ping,
	  .iov_len = sizeof ping,
	};

	message.msg_iov = &ping_vec;
	message.msg_iovlen = 1;

	return sendmsg(dst_fd, &message, 0);
}

int recvfd(int src_fd)
{
	int file_descriptors[1];
	char buffer[CMSG_SPACE(sizeof file_descriptors)];

	char ping;
	struct iovec ping_vec = {
	  .iov_base = &ping,
	  .iov_len = sizeof ping,
	};

	struct msghdr message = {
	  .msg_control = buffer,
	  .msg_controllen = sizeof buffer,
	  .msg_iov = &ping_vec,
	  .msg_iovlen = 1,
	};

	//TODO check return val
	recvmsg(src_fd, &message, 0);

	struct cmsghdr *cmessage = CMSG_FIRSTHDR(&message);
	memcpy(file_descriptors, CMSG_DATA(cmessage), sizeof file_descriptors);

	return file_descriptors[0];
}

#endif

