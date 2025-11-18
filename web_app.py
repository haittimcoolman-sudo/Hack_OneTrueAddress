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
    response = app.make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

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
                
                # Include pinellas matches if available
                pinellas_matches = result.get('pinellas_matches', [])
                response_data['pinellas_matches'] = pinellas_matches
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

@app.route('/push_updates', methods=['POST'])
def push_updates():
    """Handle push updates request to consolidate and write to internalupdates table."""
    try:
        data = request.get_json()
        pinellas_matches = data.get('pinellas_matches', [])
        
        if not pinellas_matches:
            return jsonify({
                'success': False,
                'error': 'No Pinellas matches provided.'
            }), 400
        
        # Get agent and consolidate records
        agent = get_agent()
        
        # Step 1: Consolidate the records
        consolidation_result = agent.golden_source.consolidate_pinellas_records(pinellas_matches)
        
        if consolidation_result['status'] == 'error':
            if consolidation_result.get('requires_manual_review'):
                return jsonify({
                    'success': False,
                    'error': consolidation_result['error'],
                    'requires_manual_review': True
                }), 400
            else:
                return jsonify({
                    'success': False,
                    'error': consolidation_result['error']
                }), 400
        
        # Step 2: Push the consolidated record to internalupdates table
        consolidated_record = consolidation_result['consolidated_record']
        push_result = agent.golden_source.push_to_internal_updates(consolidated_record)
        
        if push_result['status'] == 'error':
            return jsonify({
                'success': False,
                'error': push_result['error']
            }), 500
        
        return jsonify({
            'success': True,
            'message': push_result['message'],
            'consolidated_record': consolidated_record
        })
        
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

@app.after_request
def add_header(response):
    """Add headers to prevent caching of static files during development."""
    if app.debug:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

