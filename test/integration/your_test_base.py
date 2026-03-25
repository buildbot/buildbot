# Changes made to enable debugging for intermittent PB interop failures.

# Set debug for DelayedCall
from twisted.internet.base import DelayedCall

class YourTestBase:
    def setUp(self):
        # Enable DelayedCall debug
        self.original_debug = DelayedCall.debug
        DelayedCall.debug = True

    def tearDown(self):
        # Restore original DelayedCall debug
        DelayedCall.debug = self.original_debug

    def dump_delayed_calls(self):
        # This will dump the delayed calls with timing and callable information
        delayed_calls = reactor.getDelayedCalls()
        print("Delayed Calls:")
        for call in delayed_calls:
            print(f"Time: {call.getTime()}, Callable: {call.getFunction()}")

    def on_failure(self, error):
        # Check for specific errors and output PB flake summary
        if any(e in str(error) for e in ['PBConnectionLost', 'UnauthorizedLogin', 'DeadReferenceError', 'TimeoutError']):
            print("PB flake summary: Encountered PB connection issues.")
            self.dump_delayed_calls()
        # Additional failure handling here
