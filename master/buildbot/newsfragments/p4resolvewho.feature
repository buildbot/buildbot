Added callable to p4 source that allows client code to resolve the p4 user and workspace into a more complete author. 
Default behaviour is a lambda that simply returns the original supplied who. 
This callable happens after the existing regex is performed.
