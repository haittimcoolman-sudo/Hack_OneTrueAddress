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
        threshold = data.get('threshold', None)  # Get threshold from request
        
        if not input_address:
            return jsonify({
                'success': False,
                'error': 'Please enter an address to match.'
            }), 400
        
        # Get agent and match address with optional threshold
        agent = get_agent()
        result = agent.match_address(input_address, threshold=threshold)
        
        # Format the response for the UI (handles both fuzzy match and old format)
        response_data = {
            'success': True,
            'input_address': result.get('input_address', input_address),
            'candidates_searched': result.get('candidates_searched', 0),
            'confidence_threshold': result.get('confidence_threshold', 95.0),
            'search_method': result.get('search_method', 'unknown')
        }
        
        # Handle fuzzy match response format (with or without AI review)
        if result.get('search_method') in ['fuzzy_match', 'fuzzy_match_with_ai']:
            response_data['match_found'] = result.get('match_found', False)
            response_data['confidence'] = result.get('confidence', 0)
            response_data['similarity_score'] = result.get('similarity_score', 0)
            response_data['reasoning'] = result.get('reasoning', 'N/A')
            response_data['business_rule_exception'] = result.get('business_rule_exception', False)
            
            # Include Claude review if available
            if 'claude_review' in result:
                response_data['claude_review'] = result['claude_review']
            
            if response_data['match_found']:
                best_match = result.get('best_match', {})
                response_data['matched_address'] = best_match
                response_data['source_table'] = best_match.get('_source_table', 'Unknown')
                response_data['source_type'] = best_match.get('_source_type', 'unknown')
                
                # Include separate match lists for Golden Source and Internal
                golden_source_matches = result.get('golden_source_matches', [])
                internal_matches = result.get('internal_matches', [])
                
                response_data['golden_source_matches'] = golden_source_matches[:10]  # Limit to top 10
                response_data['internal_matches'] = internal_matches[:10]  # Limit to top 10
                response_data['total_golden_source'] = len(golden_source_matches)
                response_data['total_internal'] = len(internal_matches)
                response_data['has_golden_source'] = result.get('has_golden_source', False)
                response_data['has_internal'] = result.get('has_internal', False)
        else:
            # Handle legacy Claude response format (for backward compatibility)
            claude_response = result.get('claude_response', {})
            if isinstance(claude_response, dict):
                response_data['match_found'] = claude_response.get('match_found', False)
                response_data['confidence'] = claude_response.get('confidence', 'N/A')
                response_data['reasoning'] = claude_response.get('reasoning', 'N/A')
                response_data['business_rule_exception'] = claude_response.get('business_rule_exception', False)
                
                if response_data['match_found']:
                    matched_address = claude_response.get('matched_address', {})
                    response_data['matched_address'] = matched_address
                    
                    # Include internal matches if available
                    internal_matches = result.get('internal_matches', [])
                    response_data['internal_matches'] = internal_matches
                    
                    # Include exact match info
                    exact_match_info = result.get('exact_match_info', {"is_exact_match": False})
                    response_data['exact_match_info'] = exact_match_info
                    
                    # Include no internal match flag
                    no_internal_match = result.get('no_internal_match', False)
                    response_data['no_internal_match'] = no_internal_match
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
        internal_matches = data.get('internal_matches', [])
        golden_source_address = data.get('golden_source_address', {})
        scenario = data.get('scenario', 1)  # Default to scenario 1 (multiple matches)
        
        # Debug logging
        print(f"\n[Push Updates Request Debug]")
        print(f"  Request data keys: {list(data.keys())}")
        print(f"  Internal matches count: {len(internal_matches)}")
        print(f"  Golden source address keys: {list(golden_source_address.keys()) if golden_source_address else 'None'}")
        print(f"  Golden source address: {golden_source_address}")
        print(f"  Scenario: {scenario}")
        
        if not internal_matches:
            return jsonify({
                'success': False,
                'error': 'No Internal matches provided.'
            }), 400
        
        if not golden_source_address or len(golden_source_address) == 0:
            error_msg = f'No Golden Source address provided. Received: {golden_source_address}'
            print(f"  ERROR: {error_msg}")
            return jsonify({
                'success': False,
                'error': error_msg
            }), 400
        
        # Get agent and consolidate records
        agent = get_agent()
        
        # Step 1: Consolidate the records using Golden Source address
        consolidation_result = agent.golden_source.consolidate_internal_records(internal_matches, golden_source_address, scenario)
        
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
        push_result = agent.golden_source.push_to_internal_updates(consolidated_record, scenario)
        
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

@app.route('/write_to_internal', methods=['POST'])
def write_to_internal():
    """Handle writing Golden Source record to internal_updates when no internal match found."""
    try:
        data = request.get_json()
        golden_source_record = data.get('golden_source_record', {})
        
        if not golden_source_record:
            return jsonify({
                'success': False,
                'error': 'No Golden Source record provided.'
            }), 400
        
        # Get agent and write the record
        agent = get_agent()
        
        # Transform Golden Source column names to Internal table column names
        print(f"\n[Write to Internal - Transform Golden Source Record]")
        print(f"  Original Golden Source record: {golden_source_record}")
        
        internal_record = agent.golden_source._map_golden_source_to_internal(golden_source_record)
        
        print(f"  Transformed Internal record: {internal_record}")
        
        if not internal_record or len(internal_record) == 0:
            return jsonify({
                'success': False,
                'error': 'Failed to transform Golden Source record to Internal format. No valid fields found.'
            }), 400
        
        # Push the transformed record to internal_updates table
        # Scenario 3: No Internal Match (Golden Source Only)
        push_result = agent.golden_source.push_to_internal_updates(internal_record, scenario=3)
        
        if push_result['status'] == 'error':
            return jsonify({
                'success': False,
                'error': push_result['error']
            }), 500
        
        return jsonify({
            'success': True,
            'message': push_result['message'],
            'written_record': internal_record
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

