# Code context — vuln revision


## dhcpv4/nclient4/conn_unix.go (lines 72-143)

```go
  72  func udpMatch(addr *net.UDPAddr, bound *net.UDPAddr) bool {
  73  	if bound == nil {
  74  		return true
  75  	}
  76  	if bound.IP != nil && !bound.IP.Equal(addr.IP) {
  77  		return false
  78  	}
  79  	return bound.Port == addr.Port
  80  }
  81  
  82  // ReadFrom implements net.PacketConn.ReadFrom.
  83  //
  84  // ReadFrom reads raw IP packets and will try to match them against
  85  // upc.boundAddr. Any matching packets are returned via the given buffer.
  86  func (upc *BroadcastRawUDPConn) ReadFrom(b []byte) (int, net.Addr, error) {
  87  	ipHdrMaxLen := ipv4MaximumHeaderSize
  88  	udpHdrLen := udpMinimumSize
  89  
  90  	for {
  91  		pkt := make([]byte, ipHdrMaxLen+udpHdrLen+len(b))
  92  		n, _, err := upc.PacketConn.ReadFrom(pkt)
  93  		if err != nil {
  94  			return 0, nil, err
  95  		}
  96  		if n == 0 {
  97  			return 0, nil, io.EOF
  98  		}
  99  		pkt = pkt[:n]
 100  		buf := uio.NewBigEndianBuffer(pkt)
 101  
 102  		ipHdr := ipv4(buf.Data())
 103  
 104  		if !ipHdr.isValid(n) {
 105  			continue
 106  		}
 107  
 108  		ipHdr = ipv4(buf.Consume(int(ipHdr.headerLength())))
 109  
 110  		if ipHdr.transportProtocol() != udpProtocolNumber {
 111  			continue
 112  		}
 113  
 114  		if !buf.Has(udpHdrLen) {
 115  			continue
 116  		}
 117  
 118  		udpHdr := udp(buf.Consume(udpHdrLen))
 119  
 120  		addr := &net.UDPAddr{
 121  			IP:   ipHdr.destinationAddress(),
 122  			Port: int(udpHdr.destinationPort()),
 123  		}
 124  		if !udpMatch(addr, upc.boundAddr) {
 125  			continue
 126  		}
 127  		srcAddr := &net.UDPAddr{
 128  			IP:   ipHdr.sourceAddress(),
 129  			Port: int(udpHdr.sourcePort()),
 130  		}
 131  		// Extra padding after end of IP packet should be ignored,
 132  		// if not dhcp option parsing will fail.
 133  		dhcpLen := int(ipHdr.payloadLength()) - udpHdrLen
 134  		return copy(b, buf.Consume(dhcpLen)), srcAddr, nil
 135  	}
 136  }
 137  
 138  // WriteTo implements net.PacketConn.WriteTo and broadcasts all packets at the
 139  // raw socket level.
 140  //
 141  // WriteTo wraps the given packet in the appropriate UDP and IP header before
 142  // sending it on the packet conn.
 143  func (upc *BroadcastRawUDPConn) WriteTo(b []byte, addr net.Addr) (int, error) {
```
