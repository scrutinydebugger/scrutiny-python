#ifndef ___UDP_BRIDGE_H___
#define ___UDP_BRIDGE_H___

#include <system_error>

#if defined(_WIN32)
#include <winsock2.h>
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#endif



#if defined(_WIN32)
#define ISVALIDSOCKET(s) ((s) != INVALID_SOCKET)
#define CLOSESOCKET(s) closesocket(s)
#define GETSOCKETERRNO() (WSAGetLastError())
#else
#define SOCKET int
#define ISVALIDSOCKET(s) ((s) >= 0)
#define CLOSESOCKET(s) close(s)
#define GETSOCKETERRNO() (errno)
#define INVALID_SOCKET (-1)
#endif

class UdpBridge
{
 public:
    
    UdpBridge(uint16_t port);
    void start();
    void stop();
    int receive(uint8_t* buffer, int len, int flags = 0);
    void reply(const uint8_t* buffer, int len, int flags = 0);
    void set_nonblocking();
    void throw_system_error(const char* msg);

    ~UdpBridge();

  private:

    uint16_t m_port;
    SOCKET m_sock;
    
#if defined(_WIN32)
    SOCKADDR m_last_packet_addr;
    WSAData m_wsa_data;
#else
    sockaddr m_last_packet_addr;
#endif

};


#endif  // ___UDP_BRIDGE_H___