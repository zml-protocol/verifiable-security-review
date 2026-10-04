# Code context — vuln revision


## lib/server/ldap/client.go (lines 144-205)

```go
 144  // Client is an LDAP client
 145  type Client struct {
 146  	Host          string
 147  	Port          int
 148  	UseSSL        bool
 149  	AdminDN       string
 150  	AdminPassword string
 151  	Base          string
 152  	UserFilter    string               // e.g. "(uid=%s)"
 153  	GroupFilter   string               // e.g. "(memberUid=%s)"
 154  	attrNames     []string             // Names of attributes to request on an LDAP search
 155  	attrExprs     map[string]*userExpr // Expressions to evaluate to get attribute value
 156  	attrMaps      map[string]map[string]string
 157  	AdminConn     *ldap.Conn
 158  	TLS           *ctls.ClientTLSConfig
 159  	CSP           bccsp.BCCSP
 160  }
 161  
 162  // GetUser returns a user object for username and attribute values
 163  // for the requested attribute names
 164  func (lc *Client) GetUser(username string, attrNames []string) (causer.User, error) {
 165  
 166  	var sresp *ldap.SearchResult
 167  	var err error
 168  
 169  	log.Debugf("Getting user '%s'", username)
 170  
 171  	// Search for the given username
 172  	sreq := ldap.NewSearchRequest(
 173  		lc.Base, ldap.ScopeWholeSubtree,
 174  		ldap.NeverDerefAliases, 0, 0, false,
 175  		fmt.Sprintf(lc.UserFilter, username),
 176  		lc.attrNames,
 177  		nil,
 178  	)
 179  
 180  	// Try to search using the cached connection, if there is one
 181  	conn := lc.AdminConn
 182  	if conn != nil {
 183  		log.Debugf("Searching for user '%s' using cached connection", username)
 184  		sresp, err = conn.Search(sreq)
 185  		if err != nil {
 186  			log.Debugf("LDAP search failed but will close connection and try again; error was: %s", err)
 187  			conn.Close()
 188  			lc.AdminConn = nil
 189  		}
 190  	}
 191  
 192  	// If there was no cached connection or the search failed for any reason
 193  	// (including because the server may have closed the cached connection),
 194  	// try with a new connection.
 195  	if sresp == nil {
 196  		log.Debugf("Searching for user '%s' using new connection", username)
 197  		conn, err = lc.newConnection()
 198  		if err != nil {
 199  			return nil, err
 200  		}
 201  		sresp, err = conn.Search(sreq)
 202  		if err != nil {
 203  			conn.Close()
 204  			return nil, errors.Wrapf(err, "LDAP search failure; search request: %+v", sreq)
 205  		}
```
