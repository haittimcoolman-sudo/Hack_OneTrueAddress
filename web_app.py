"""Flask web application for OneTrueAddress agent."""
from flask import Flask, render_template, request, jsonify
from address_agent import AddressAgent
import traceback
import atexit

app = Flask(__name__)

# Global agent instance (initialized on first use)
agent = None

def get_agent():
    """Get or create the address agent instance."""
    global agent
    if agent is None:
        agent = AddressAgent()
    return agent

def cleanup_agent():
    """Clean up the agent on application shutdown."""
    global agent
    if agent is not None:
        try:
            agent.close()
        except:
            pass

# Register cleanup function
atexit.register(cleanup_agent)

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/match', methods=['POST'])
def match_address():
    """Handle address matching request."""
    try:
        data = request.get_json()
        input_address = data.get('address', '').strip()
        
        if not input_address:
            return jsonify({
                'success': False,
                'error': 'Please enter an address to match.'
            }), 400
        
        # Get agent and match address
        agent = get_agent()
        result = agent.match_address(input_address)
        
        # Format the response for the UI
        response_data = {
            'success': True,
            'input_address': result.get('input_address', input_address),
            'candidates_searched': result.get('candidates_searched', 0),
            'confidence_threshold': result.get('confidence_threshold', 90.0)
        }
        
        claude_response = result.get('claude_response', {})
        if isinstance(claude_response, dict):
            response_data['match_found'] = claude_response.get('match_found', False)
            response_data['confidence'] = claude_response.get('confidence', 'N/A')
            response_data['reasoning'] = claude_response.get('reasoning', 'N/A')
            response_data['business_rule_exception'] = claude_response.get('business_rule_exception', False)
            
            if response_data['match_found']:
                matched_address = claude_response.get('matched_address', {})
                response_data['matched_address'] = matched_address
        else:
            response_data['match_found'] = False
            response_data['raw_response'] = result.get('raw_response', 'No response')
        
        return jsonify(response_data)
        
    except Exception as e:
        error_msg = str(e)
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': error_msg
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

