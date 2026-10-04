# Code context — fixed revision


## lib/server/ldap/client.go (lines 144-205)

```go
 144  // Connection to an LDAP server.
 145  type Connection interface {
 146  	// Search using the given search request.
 147  	Search(searchRequest *ldap.SearchRequest) (*ldap.SearchResult, error)
 148  	// Close the connection.
 149  	Close() error
 150  }
 151  
 152  // Client is an LDAP client
 153  type Client struct {
 154  	Host          string
 155  	Port          int
 156  	UseSSL        bool
 157  	AdminDN       string
 158  	AdminPassword string
 159  	Base          string
 160  	UserFilter    string               // e.g. "(uid=%s)"
 161  	GroupFilter   string               // e.g. "(memberUid=%s)"
 162  	attrNames     []string             // Names of attributes to request on an LDAP search
 163  	attrExprs     map[string]*userExpr // Expressions to evaluate to get attribute value
 164  	attrMaps      map[string]map[string]string
 165  	AdminConn     Connection
 166  	TLS           *ctls.ClientTLSConfig
 167  	CSP           bccsp.BCCSP
 168  }
 169  
 170  // GetUser returns a user object for username and attribute values
 171  // for the requested attribute names
 172  func (lc *Client) GetUser(username string, attrNames []string) (causer.User, error) {
 173  
 174  	var sresp *ldap.SearchResult
 175  	var err error
 176  
 177  	log.Debugf("Getting user '%s'", username)
 178  
 179  	// Search for the given username
 180  	escapedUsername := ldap.EscapeFilter(username)
 181  	sreq := ldap.NewSearchRequest(
 182  		lc.Base, ldap.ScopeWholeSubtree,
 183  		ldap.NeverDerefAliases, 0, 0, false,
 184  		fmt.Sprintf(lc.UserFilter, escapedUsername),
 185  		lc.attrNames,
 186  		nil,
 187  	)
 188  
 189  	// Try to search using the cached connection, if there is one
 190  	conn := lc.AdminConn
 191  	if conn != nil {
 192  		log.Debugf("Searching for user '%s' using cached connection", username)
 193  		sresp, err = conn.Search(sreq)
 194  		if err != nil {
 195  			log.Debugf("LDAP search failed but will close connection and try again; error was: %s", err)
 196  			conn.Close()
 197  			lc.AdminConn = nil
 198  		}
 199  	}
 200  
 201  	// If there was no cached connection or the search failed for any reason
 202  	// (including because the server may have closed the cached connection),
 203  	// try with a new connection.
 204  	if sresp == nil {
 205  		log.Debugf("Searching for user '%s' using new connection", username)
```
