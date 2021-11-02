#ifndef ___UDP_BRIDGE_H___
#define ___UDP_BRIDGE_H___

#include <system_error>
#include <winsock2.h>
#include <thread>

class UdpBridge
{
 public:
     UdpBridge(uint16_t port);
    void start();
    void close();
    int receive(uint8_t* buffer, int len, int flags = 0);
    void reply(const uint8_t* buffer, int len, int flags = 0);

    ~UdpBridge();

  private:

    uint16_t m_port;

    SOCKET m_sock;
    SOCKADDR m_last_packet_addr;
    WSAData m_wsa_data;


};


#endif  // ___UDP_BRIDGE_H___