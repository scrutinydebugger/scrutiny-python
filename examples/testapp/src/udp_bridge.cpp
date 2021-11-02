#include "udp_bridge.h"
#include <thread>
#include <chrono>

UdpBridge::UdpBridge(uint16_t port) :
    m_sock(INVALID_SOCKET),
    m_port(port)
{
    int ret = WSAStartup(MAKEWORD(2, 2), &m_wsa_data);
    if (ret != 0)
    {
        throw std::system_error(WSAGetLastError(), std::system_category(), "WSAStartup Failed");
    }
}

void UdpBridge::start()
{
    int ret;

    m_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (m_sock == INVALID_SOCKET)
    {
        throw std::system_error(WSAGetLastError(), std::system_category(), "Error opening socket");
    }

    u_long mode = 1;    // Non-blocking
    ret = ioctlsocket(m_sock, FIONBIO, &mode);
    if (ret != NO_ERROR)
    {
        throw std::system_error(WSAGetLastError(), std::system_category(), "ioctlsocket failed");
    }

    sockaddr_in addr;
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    addr.sin_port = htons(m_port);

    ret = bind(m_sock, reinterpret_cast<SOCKADDR*>(&addr), sizeof(addr));
    if (ret < 0)
    {
        throw std::system_error(WSAGetLastError(), std::system_category(), "Bind failed");
    }
}



void UdpBridge::close()
{
    if (m_sock != INVALID_SOCKET)
    {
        closesocket(m_sock);
    }
}

UdpBridge::~UdpBridge()
{
    WSACleanup();
}

int UdpBridge::receive(uint8_t* buffer, int len, int flags)
{ 
    int size = sizeof(m_last_packet_addr);
    int ret = recvfrom(m_sock, reinterpret_cast<char*>(buffer), len, flags, &m_last_packet_addr, &size);
    
    if (ret < 0)
    {
        int errorcode = WSAGetLastError();
        if (errorcode == WSAEWOULDBLOCK)
        {
            ret = 0;
        }
        else
        {
            throw std::system_error(errorcode, std::system_category(), "recvfrom failed");
        }
    }

    return ret;
}


 void UdpBridge::reply(const uint8_t* buffer, int len, int flags)
 {
   int ret = sendto(m_sock, reinterpret_cast<const char*>(buffer), len, flags, &m_last_packet_addr, sizeof(m_last_packet_addr));
   if (ret < 0)
   {
        throw std::system_error(WSAGetLastError(), std::system_category(), "sendto failed");
   }
 }
 