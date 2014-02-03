package server

import (
	"bytes"
	"github.com/nelhage/livegrep/config"
	"html/template"
	"io"
	"path"
)

type templates struct {
	layout,
	searchPage,
	aboutPage,
	opensearchXML *template.Template
}

type page struct {
	IncludeJS  bool
	Production bool
	Title      string
	Body       template.HTML
}

type opensearchContext struct {
	BackendName string
	BaseURL     string
}

type searchContext struct {
	GithubRepos interface{}
	Backends    []config.Backend
}

func (s *server) readTemplates(files ...string) *template.Template {
	filenames := make([]string, 0, len(files))
	for _, f := range files {
		filenames = append(filenames, path.Join(s.config.DocRoot, "templates", f))
	}
	return template.Must(template.ParseFiles(filenames...))
}

func (s *server) executeTemplate(t *template.Template, context interface{}) ([]byte, error) {
	var buf bytes.Buffer
	if err := t.Execute(&buf, context); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

func (s *server) renderPage(w io.Writer, p *page) {
	p.Production = s.config.Production
	s.t.layout.Execute(w, p)

}
