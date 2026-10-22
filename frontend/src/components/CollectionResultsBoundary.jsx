import { Component } from 'react'

export default class CollectionResultsBoundary extends Component {
    state = { error: null }

    static getDerivedStateFromError(error) {
        return { error }
    }

    componentDidUpdate(previousProps) {
        if (previousProps.jobId !== this.props.jobId && this.state.error) {
            this.setState({ error: null })
        }
    }

    render() {
        if (!this.state.error) return this.props.children
        return (
            <div className="collection-card collection-warning" role="alert">
                <h3>The collection finished, but its result view could not be displayed</h3>
                <p>The rest of KlinkPPI is still available. Start a new collection search or reload this result.</p>
                <details>
                    <summary>Technical detail</summary>
                    <code>{this.state.error.message || String(this.state.error)}</code>
                </details>
            </div>
        )
    }
}
