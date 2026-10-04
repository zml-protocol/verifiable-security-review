# Code context — fixed revision


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
 114  		// The IPv4 payload must be large enough to hold a UDP header. Discarding
 115  		// frames that declare fewer bytes keeps the DHCP length computed below
 116  		// non-negative and avoids parsing trailing padding as a UDP header.
 117  		ipPayloadLen := int(ipHdr.payloadLength())
 118  		if ipPayloadLen < udpHdrLen {
 119  			continue
 120  		}
 121  
 122  		if !buf.Has(udpHdrLen) {
 123  			continue
 124  		}
 125  
 126  		udpHdr := udp(buf.Consume(udpHdrLen))
 127  
 128  		addr := &net.UDPAddr{
 129  			IP:   ipHdr.destinationAddress(),
 130  			Port: int(udpHdr.destinationPort()),
 131  		}
 132  		if !udpMatch(addr, upc.boundAddr) {
 133  			continue
 134  		}
 135  		srcAddr := &net.UDPAddr{
 136  			IP:   ipHdr.sourceAddress(),
 137  			Port: int(udpHdr.sourcePort()),
 138  		}
 139  		// Extra padding after the end of the IP payload is ignored; otherwise
 140  		// dhcp option parsing would fail.
 141  		dhcpLen := ipPayloadLen - udpHdrLen
 142  		if !buf.Has(dhcpLen) {
 143  			continue
```
