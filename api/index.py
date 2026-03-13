"""
Flask API for ClerKase
Main application entry point
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import components
from state_manager import get_state_manager, SectionStatus
from input_parser import get_input_parser
from clarification_engine import get_clarification_engine
from document_compiler import get_document_compiler

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Enable CORS
CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Initialize components
state_manager = get_state_manager()
input_parser = get_input_parser()
clarification_engine = get_clarification_engine(use_ai=True)
document_compiler = get_document_compiler('/tmp/exports')


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad request", "message": str(error)}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found", "message": str(error)}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error", "message": str(error)}), 500


# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    })


@app.route('/api/status', methods=['GET'])
def system_status():
    """Get system status"""
    ai_status = clarification_engine.get_ai_status()
    
    return jsonify({
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "state_manager": "active",
            "input_parser": "active",
            "clarification_engine": "active",
            "ai_clarifier": ai_status,
            "document_compiler": "active"
        },
        "available_rotations": state_manager.get_available_rotations()
    })


# ============================================================================
# ROTATION ENDPOINTS
# ============================================================================

@app.route('/api/rotations', methods=['GET'])
def get_rotations():
    """Get all available rotations"""
    rotations = state_manager.get_available_rotations()
    
    rotation_list = []
    for rotation in rotations:
        template = state_manager.get_template(rotation)
        if template:
            rotation_list.append({
                "id": rotation,
                "name": rotation.replace("_", " ").title(),
                "section_count": len(template.get("sections", [])),
                "version": template.get("version", "1.0")
            })
    
    return jsonify({
        "rotations": rotation_list
    })


@app.route('/api/rotations/<rotation_id>', methods=['GET'])
def get_rotation_detail(rotation_id):
    """Get detailed information about a rotation"""
    template = state_manager.get_template(rotation_id)
    
    if not template:
        return jsonify({"error": "Rotation not found"}), 404
    
    sections = sorted(template.get("sections", []), key=lambda s: s.get("order", 999))
    
    return jsonify({
        "id": rotation_id,
        "name": rotation_id.replace("_", " ").title(),
        "version": template.get("version", "1.0"),
        "sections": [
            {
                "name": s.get("name"),
                "title": s.get("title"),
                "order": s.get("order"),
                "required": s.get("required", True),
                "field_count": len(s.get("fields", []))
            }
            for s in sections
        ]
    })


@app.route('/api/rotations/<rotation_id>/template', methods=['GET'])
def get_rotation_template(rotation_id):
    """Get full template for a rotation"""
    template = state_manager.get_template(rotation_id)
    
    if not template:
        return jsonify({"error": "Rotation not found"}), 404
    
    return jsonify(template)


@app.route('/api/rotations/<rotation_id>/sections/<section_name>', methods=['GET'])
def get_section_template(rotation_id, section_name):
    """Get template for a specific section"""
    template = state_manager.get_template(rotation_id)
    
    if not template:
        return jsonify({"error": "Rotation not found"}), 404
    
    for section in template.get("sections", []):
        if section.get("name") == section_name:
            return jsonify(section)
    
    return jsonify({"error": "Section not found"}), 404


# ============================================================================
# CASE MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/api/cases', methods=['POST'])
def create_case():
    """Create a new case"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    rotation = data.get('rotation')
    
    if not rotation:
        return jsonify({"error": "Rotation is required"}), 400
    
    try:
        case_state = state_manager.create_case(rotation)
        
        return jsonify({
            "message": "Case created successfully",
            "case": {
                "case_id": case_state.case_id,
                "rotation": case_state.rotation,
                "current_section": case_state.current_section,
                "created_at": case_state.created_at,
                "is_complete": case_state.is_complete
            }
        }), 201
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to create case: {str(e)}"}), 500


@app.route('/api/cases', methods=['GET'])
def list_cases():
    """List all cases"""
    cases = state_manager.get_all_cases()
    
    return jsonify({
        "cases": cases,
        "total": len(cases)
    })


@app.route('/api/cases/<case_id>', methods=['GET'])
def get_case(case_id):
    """Get case details"""
    case_state = state_manager.get_case(case_id)
    
    if not case_state:
        return jsonify({"error": "Case not found"}), 404
    
    return jsonify(case_state.to_dict())


@app.route('/api/cases/<case_id>', methods=['DELETE'])
def delete_case(case_id):
    """Delete a case"""
    success = state_manager.delete_case(case_id)
    
    if not success:
        return jsonify({"error": "Case not found"}), 404
    
    return jsonify({
        "message": "Case deleted successfully",
        "case_id": case_id
    })


# ============================================================================
# SECTION ENDPOINTS
# ============================================================================

@app.route('/api/cases/<case_id>/sections/<section_name>', methods=['GET'])
def get_section(case_id, section_name):
    """Get section data"""
    case_state = state_manager.get_case(case_id)
    
    if not case_state:
        return jsonify({"error": "Case not found"}), 404
    
    if section_name not in case_state.sections:
        return jsonify({"error": "Section not found"}), 404
    
    section = case_state.sections[section_name]
    
    return jsonify({
        "case_id": case_id,
        "section_name": section_name,
        "data": section.data,
        "status": section.status,
        "pending_clarifications": section.pending_clarifications
    })


@app.route('/api/cases/<case_id>/sections/<section_name>', methods=['PUT'])
def update_section(case_id, section_name):
    """Update section data"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    case_state = state_manager.get_case(case_id)
    
    if not case_state:
        return jsonify({"error": "Case not found"}), 404
    
    if section_name not in case_state.sections:
        return jsonify({"error": "Section not found"}), 404
    
    section_data = data.get('data', {})
    status = data.get('status')
    
    try:
        case_state = state_manager.update_section(
            case_id, section_name, section_data, status
        )
        
        return jsonify({
            "message": "Section updated successfully",
            "case_id": case_id,
            "section_name": section_name,
            "status": case_state.sections[section_name].status
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to update section: {str(e)}"}), 500


@app.route('/api/cases/<case_id>/sections/<section_name>/submit', methods=['POST'])
def submit_section(case_id, section_name):
    """Submit section data and get clarifications"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    case_state = state_manager.get_case(case_id)
    
    if not case_state:
        return jsonify({"error": "Case not found"}), 404
    
    if section_name not in case_state.sections:
        return jsonify({"error": "Section not found"}), 404
    
    section_data = data.get('data', {})
    
    try:
        # Update section data
        case_state = state_manager.update_section(
            case_id, section_name, section_data, SectionStatus.IN_PROGRESS.value
        )
        
        # Get template
        template = state_manager.get_template(case_state.rotation)
        
        # Get all sections for context
        all_sections = {
            name: {"data": s.data} 
            for name, s in case_state.sections.items()
        }
        
        # Process clarifications
        clarification_result = clarification_engine.process_section(
            case_id=case_id,
            section_name=section_name,
            section_data=section_data,
            template=template,
            all_sections=all_sections
        )
        
        # If clarifications needed, add them to section
        if clarification_result.questions:
            case_state = state_manager.add_clarifications(
                case_id, section_name, clarification_result.questions
            )
            
            return jsonify({
                "message": "Clarifications needed",
                "case_id": case_id,
                "section_name": section_name,
                "clarifications_needed": True,
                "questions": clarification_result.questions,
                "source": clarification_result.source,
                "confidence": clarification_result.confidence
            })
        
        # No clarifications needed - mark as complete
        case_state = state_manager.update_section(
            case_id, section_name, section_data, SectionStatus.COMPLETE.value
        )
        
        # Add to completed sections
        if section_name not in case_state.completed_sections:
            case_state.completed_sections.append(section_name)
        
        return jsonify({
            "message": "Section submitted successfully",
            "case_id": case_id,
            "section_name": section_name,
            "clarifications_needed": False,
            "status": SectionStatus.COMPLETE.value
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to submit section: {str(e)}"}), 500


@app.route('/api/cases/<case_id>/sections/<section_name>/clarifications', methods=['POST'])
def answer_clarifications(case_id, section_name):
    """Submit answers to clarification questions"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    case_state = state_manager.get_case(case_id)
    
    if not case_state:
        return jsonify({"error": "Case not found"}), 404
    
    if section_name not in case_state.sections:
        return jsonify({"error": "Section not found"}), 404
    
    answers = data.get('answers', {})
    
    try:
        # Merge answers into section data
        section = case_state.sections[section_name]
        updated_data = {**section.data, **answers}
        
        # Clear clarifications and mark as complete
        case_state = state_manager.update_section(
            case_id, section_name, updated_data, SectionStatus.COMPLETE.value
        )
        case_state = state_manager.clear_clarifications(case_id, section_name)
        
        # Add to completed sections
        if section_name not in case_state.completed_sections:
            case_state.completed_sections.append(section_name)
        
        return jsonify({
            "message": "Clarifications answered successfully",
            "case_id": case_id,
            "section_name": section_name,
            "status": SectionStatus.COMPLETE.value
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to answer clarifications: {str(e)}"}), 500


@app.route('/api/cases/<case_id>/sections/<section_name>/skip', methods=['POST'])
def skip_section(case_id, section_name):
    """Skip a section (mark as not applicable)"""
    case_state = state_manager.get_case(case_id)
    
    if not case_state:
        return jsonify({"error": "Case not found"}), 404
    
    if section_name not in case_state.sections:
        return jsonify({"error": "Section not found"}), 404
    
    try:
        # Mark section as skipped (complete with empty data)
        case_state = state_manager.update_section(
            case_id, section_name, {"_skipped": True}, SectionStatus.COMPLETE.value
        )
        
        # Add to completed sections
        if section_name not in case_state.completed_sections:
            case_state.completed_sections.append(section_name)
        
        return jsonify({
            "message": "Section skipped successfully",
            "case_id": case_id,
            "section_name": section_name,
            "status": SectionStatus.COMPLETE.value
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to skip section: {str(e)}"}), 500


# ============================================================================
# WORKFLOW ENDPOINTS
# ============================================================================

@app.route('/api/cases/<case_id>/next', methods=['POST'])
def move_to_next_section(case_id):
    """Move to next section in workflow"""
    case_state = state_manager.get_case(case_id)
    
    if not case_state:
        return jsonify({"error": "Case not found"}), 404
    
    try:
        case_state = state_manager.move_to_next_section(case_id)
        
        return jsonify({
            "message": "Moved to next section",
            "case_id": case_id,
            "current_section": case_state.current_section,
            "is_complete": case_state.is_complete,
            "completed_sections": case_state.completed_sections
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to move to next section: {str(e)}"}), 500


@app.route('/api/cases/<case_id>/progress', methods=['GET'])
def get_progress(case_id):
    """Get case progress"""
    try:
        progress = state_manager.get_progress(case_id)
        return jsonify(progress)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to get progress: {str(e)}"}), 500


# ============================================================================
# PARSING ENDPOINTS
# ============================================================================

@app.route('/api/parse', methods=['POST'])
def parse_input():
    """Parse clinical input text"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    text = data.get('text')
    section = data.get('section', 'general')
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    try:
        result = input_parser.parse(text, section)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Failed to parse input: {str(e)}"}), 500


@app.route('/api/parse/socrates', methods=['POST'])
def parse_socrates():
    """Parse SOCRATES pain assessment"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    text = data.get('text')
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    try:
        socrates = input_parser._extract_socrates_pain(text)
        
        if socrates:
            return jsonify(socrates.to_dict())
        else:
            return jsonify({
                "site": None,
                "onset": None,
                "character": None,
                "radiation": None,
                "associations": None,
                "time_course": None,
                "exacerbating": None,
                "relieving": None,
                "severity": None,
                "is_complete": False
            })
    except Exception as e:
        return jsonify({"error": f"Failed to parse SOCRATES: {str(e)}"}), 500


# ============================================================================
# CLARIFICATION ENDPOINTS
# ============================================================================

@app.route('/api/clarify', methods=['POST'])
def generate_clarifications():
    """Generate clarifications for section data"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    section_name = data.get('section_name')
    section_data = data.get('section_data', {})
    rotation = data.get('rotation')
    
    if not section_name or not rotation:
        return jsonify({"error": "section_name and rotation are required"}), 400
    
    try:
        template = state_manager.get_template(rotation)
        
        if not template:
            return jsonify({"error": "Rotation not found"}), 404
        
        result = clarification_engine.process_section(
            case_id="temp",
            section_name=section_name,
            section_data=section_data,
            template=template
        )
        
        return jsonify({
            "questions": result.questions,
            "source": result.source,
            "confidence": result.confidence,
            "reasoning": result.reasoning
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to generate clarifications: {str(e)}"}), 500


@app.route('/api/clarify/contradictions', methods=['POST'])
def detect_contradictions():
    """Detect contradictions across sections"""
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    sections = data.get('sections', {})
    
    try:
        contradictions = clarification_engine.detect_contradictions(sections)
        
        return jsonify({
            "contradictions_found": len(contradictions) > 0,
            "contradictions": contradictions
        })
        
    except Exception as e:
        return jsonify({"error": f"Failed to detect contradictions: {str(e)}"}), 500


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@app.route('/api/cases/<case_id>/export', methods=['POST'])
def export_case(case_id):
    """Export case to document"""
    data = request.get_json() or {}
    
    format_type = data.get('format', 'markdown')
    include_sections = data.get('sections')
    
    case_state = state_manager.get_case(case_id)
    
    if not case_state:
        return jsonify({"error": "Case not found"}), 404
    
    try:
        case_data = case_state.to_dict()
        
        if format_type == 'markdown':
            result = document_compiler.compile_markdown(
                case_id, case_data, include_sections
            )
        elif format_type == 'word':
            result = document_compiler.compile_word(
                case_id, case_data, include_sections
            )
        else:
            return jsonify({"error": "Invalid format. Use 'markdown' or 'word'"}), 400
        
        if result.success:
            return jsonify({
                "message": f"Case exported to {format_type} successfully",
                "case_id": case_id,
                "format": format_type,
                "file_path": result.file_path,
                "content": result.content if format_type == 'markdown' else None
            })
        else:
            return jsonify({"error": result.error}), 500
            
    except Exception as e:
        return jsonify({"error": f"Failed to export case: {str(e)}"}), 500


@app.route('/api/cases/<case_id>/export/download', methods=['GET'])
def download_export(case_id):
    """Download exported case document"""
    format_type = request.args.get('format', 'markdown')
    
    if format_type == 'markdown':
        file_path = os.path.join(document_compiler.output_dir, f"{case_id}.md")
        mimetype = 'text/markdown'
    elif format_type == 'word':
        file_path = os.path.join(document_compiler.output_dir, f"{case_id}.docx")
        mimetype = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    else:
        return jsonify({"error": "Invalid format"}), 400
    
    if not os.path.exists(file_path):
        return jsonify({"error": "Export not found. Please export the case first"}), 404
    
    from flask import send_file
    return send_file(
        file_path,
        mimetype=mimetype,
        as_attachment=True,
        download_name=f"clerkase_{case_id}.{format_type if format_type == 'markdown' else 'docx'}"
    )


@app.route('/api/cases/<case_id>/summary', methods=['GET'])
def get_case_summary(case_id):
    """Get brief case summary"""
    case_state = state_manager.get_case(case_id)
    
    if not case_state:
        return jsonify({"error": "Case not found"}), 404
    
    try:
        case_data = case_state.to_dict()
        result = document_compiler.compile_case_summary(case_id, case_data)
        
        if result.success:
            return jsonify({
                "case_id": case_id,
                "summary": result.content
            })
        else:
            return jsonify({"error": result.error}), 500
            
    except Exception as e:
        return jsonify({"error": f"Failed to generate summary: {str(e)}"}), 500


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('case_storage', exist_ok=True)
    os.makedirs('exports', exist_ok=True)
    
    # Get port from environment or use default
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ClerKase - AI-Powered Clinical Clerking Assistant          ║
║                                                              ║
║   API Server Starting...                                     ║
║                                                              ║
║   Port: {port:<5}                                              ║
║   Debug: {str(debug):<5}                                             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=port, debug=debug)
